/* SPDX-License-Identifier: GPL-2.0-or-later */
#import "../openstep/BrowserWindowController.h"
#import "PlotView.h"
#import "text.h"
#import "schedule.h"
#import <appkit/NXCursor.h>
#import <appkit/ClipView.h>
#import <appkit/Cell.h>
#import <dpsclient/psops.h>
#include "netsurf/browser_window.h"
#include "netsurf/keypress.h"
#include "netsurf/misc.h"
#include "desktop/browser_history.h"
#include "utils/nsurl.h"
#include "utils/log.h"

static id pending_target;
NSMutableArray *nextstep_browser_windows;

@interface BrowserWindowController (LocationEditing)
- (void)finishLocationEditing;
- (void)browserViewDidResize;
- (void)enterUrl:(id)sender;
- windowWillClose:sender;
- windowDidResize:sender;
@end

/* Old AppKit sends Object's target/action messages, including perform:with:.
 * Keep that protocol on a native Object rather than relying on Foundation's
 * distinct NSObject protocol. The controller owns this weak action adapter. */
@interface NextstepWindowActions : Object {
	BrowserWindowController *controller;
}
- initWithController:(BrowserWindowController *)value;
@end
@implementation NextstepWindowActions
- initWithController:(BrowserWindowController *)value
{
	self = [super init];
	controller = value;
	return self;
}
- enterUrl:sender { [controller enterUrl:sender]; return self; }
- back:sender { [controller back:sender]; return self; }
- forward:sender { [controller forward:sender]; return self; }
- stopOrRefresh:sender { [controller stopOrRefresh:sender]; return self; }
- windowWillClose:sender { [controller windowWillClose:sender]; return self; }
- windowDidResize:sender { [controller windowDidResize:sender]; return self; }
@end
static void finish_location_editing(void *context)
{
	[(BrowserWindowController *)context finishLocationEditing];
}

/* A plain View does not erase its background. The toolbar must repaint the
 * strip uncovered when it moves during a buffered-window resize. */
@interface NextstepToolbarView : View
@end
@implementation NextstepToolbarView
- initFrame:(const NXRect *)rect
{
	self = [super initFrame:rect];
	[self setOpaque:YES];
	return self;
}
- drawSelf:(const NXRect *)rects :(int)count
{
	int i;
	PSsetgray(NX_LTGRAY);
	for (i = 0; i < count; i++) NXRectFill(&rects[i]);
	return self;
}
@end

/* A single opaque view keeps the activity bar independent of text controls.
 * Its width follows the address field; an idle bar erases its previous pixels. */
@interface NextstepProgressView : NextstepToolbarView { float progress; BOOL pending; }
- setProgress:(float)value;
- displayPendingContent;
@end
@implementation NextstepProgressView
- setProgress:(float)value
{
	progress = value;
	pending = YES;
	[self setNeedsDisplay:YES];
	return self;
}
- displayPendingContent
{
	if (pending && [self canDraw]) [self display];
	return self;
}
- drawSelf:(const NXRect *)rects :(int)count
{
	NXRect bounds;
	pending = NO;
	[super drawSelf:rects :count];
	if (progress <= 0) return self;
	[self getBounds:&bounds];
	PSsetgray(.75);
	NXRectFill(&bounds);
	bounds.size.width *= progress;
	PSsetgray(NX_DKGRAY);
	NXRectFill(&bounds);
	return self;
}
@end

static NXImage *toolbar_image(NSString *name)
{
	NSString *path = [[NSBundle mainBundle] pathForResource:name ofType:@"tiff"];
	/* NEXTSTEP's Foundation bundle lookup does not consistently search the
	 * OPENSTEP-style Resources directory. Keep the shared bundle layout. */
	if (path == nil) path = [[[NSBundle mainBundle] bundlePath]
		stringByAppendingPathComponent:[NSString stringWithFormat:@"Resources/%@.tiff", name]];
	return [[NXImage alloc] initFromFile:[path cString]];
}
static void button_image(Button *control, NXImage *image, const char *fallback)
{
	[control setImage:image];
	[control setIconPosition:image ? NX_ICONONLY : NX_TITLEONLY];
	[control setTitle:image ? "" : fallback];
}

/* sizeWindow:: resizes the view hierarchy without necessarily delivering the
 * interactive window delegate notification. Observe the content view itself. */
@interface NextstepContentView : NextstepToolbarView {
	id browserController;
}
- setBrowserController:controller;
@end
@implementation NextstepContentView
- setBrowserController:controller
{
	browserController = controller;
	return self;
}
- resizeSubviews:(const NXSize *)oldSize
{
	[super resizeSubviews:oldSize];
	[browserController browserViewDidResize];
	return self;
}
@end

static Button *button(View *parent, id target, const char *title, SEL action,
		float x, float width)
{
	NXRect rect = NSMakeRect(x, 6, width, 40);
	Button *control = [[Button alloc] initFrame:&rect];
	[control setTitle:title];
	[control setTarget:target];
	[control setAction:action];
	[parent addSubview:control];
	return control;
}

@implementation BrowserWindowController
+ (id)pendingBrowserTarget { return pending_target; }
+ (void)setPendingBrowserTarget:(id)target { pending_target = target; }
- (id)initWithBrowser:(struct browser_window *)value
{
	self = [super init];
	if (self != nil) {
		browser = value;
		openstepScale = 1;
		backImage = toolbar_image(@"Left");
		forwardImage = toolbar_image(@"Right");
		reloadImage = toolbar_image(@"Reload");
		stopImage = toolbar_image(@"Stop");
		if (nextstep_browser_windows == nil)
			nextstep_browser_windows = [NSMutableArray new];
		[nextstep_browser_windows addObject:self];
	}
	return self;
}
- (void)loadWindow
{
	NXSize screen;
	float width = 720, height = 480;
	NXRect rect;
	View *content, *toolbar;
	[NXApp getScreenSize:&screen];
	/* Leave the application menu and Workspace dock clear, including VGA. */
	if (screen.width > 0 && screen.width < 940) width = screen.width - 220;
	if (screen.height > 0 && screen.height < 560) height = screen.height - 80;
	if (width < 320) width = 320;
	if (height < 240) height = 240;
	rect = NSMakeRect(140, 40, width, height);
	if (window != nil) return;
	window = [[Window alloc] initContent:&rect style:NX_RESIZEBARSTYLE
		backing:NX_BUFFERED buttonMask:NX_CLOSEBUTTONMASK | NX_MINIATURIZEBUTTONMASK
		defer:NO];
	[(Window *)window setTitle:"NetSurf"];
	[window setFreeWhenClosed:NO];
	nativeActionTarget = [[NextstepWindowActions alloc] initWithController:self];
	[window setDelegate:nativeActionTarget];
	{
		NXSize minimum = NSMakeSize(360, 240);
		[window setMinSize:&minimum];
	}
	[window addToEventMask:NX_MOUSEMOVEDMASK | NX_LMOUSEDRAGGEDMASK | NX_LMOUSEUPMASK];
	rect = NSMakeRect(0, 0, width, height);
	content = [[NextstepContentView alloc] initFrame:&rect];
	[window setContentView:content];
	rect = NSMakeRect(0, height - 52, width, 52);
	toolbar = [[NextstepToolbarView alloc] initFrame:&rect];
	[toolbar setAutoresizeSubviews:YES];
	[toolbar setAutosizing:NX_WIDTHSIZABLE | NX_MINYMARGINSIZABLE];
	[content addSubview:toolbar];
	backButton = button(toolbar, nativeActionTarget, "Back", @selector(back:), 6, 40);
	button_image(backButton, backImage, "Back");
	forwardButton = button(toolbar, nativeActionTarget, "Forward", @selector(forward:), 50, 40);
	button_image(forwardButton, forwardImage, "Next");
	refreshButton = button(toolbar, nativeActionTarget, "Reload", @selector(stopOrRefresh:), width - 46, 40);
	[refreshButton setAutosizing:NX_MINXMARGINSIZABLE];
	button_image(refreshButton, reloadImage, "Load");
	rect = NSMakeRect(102, 19, width - 156, 22);
	urlBar = [[TextField alloc] initFrame:&rect];
	[urlBar setBezeled:YES];
	/* Native setSelectable:YES clears editability. setEditable:YES already
	 * enables selection as well as typing and paste. */
	[urlBar setEditable:YES];
	[urlBar setTarget:nativeActionTarget];
	[urlBar setAction:@selector(enterUrl:)];
	[urlBar setAutosizing:NX_WIDTHSIZABLE];
	[toolbar addSubview:urlBar];
	rect = NSMakeRect(102, 12, width - 156, 4);
	progressTrack = [[NextstepProgressView alloc] initFrame:&rect];
	[progressTrack setAutosizing:NX_WIDTHSIZABLE];
	[toolbar addSubview:progressTrack];
	rect = NSMakeRect(0, 0, width, height - 52);
	scrollView = [[ScrollView alloc] initFrame:&rect];
	[scrollView setAutosizing:NX_WIDTHSIZABLE | NX_HEIGHTSIZABLE];
	[scrollView setVertScrollerRequired:YES];
	[scrollView setHorizScrollerRequired:YES];
	[scrollView setDynamicScrolling:YES];
	[scrollView setCopyOnScroll:NO];
	[scrollView setDisplayOnScroll:YES];
	[scrollView setLineScroll:20];
	[content addSubview:scrollView];
	plotView = [[NextstepPlotView alloc] initFrame:&rect];
	[plotView setBrowser:browser];
	[scrollView setDocView:plotView];
	[content setAutoresizeSubviews:YES];
	nativeViewportSize = [self getBrowserSize];
	[(NextstepContentView *)content setBrowserController:self];
	[window makeFirstResponder:plotView];
	[window display];
	[window makeKeyAndOrderFront:self];
	[window flushWindow];
}
- (void)attachBrowser:(struct browser_window *)value
{
	browser = value;
	[plotView setBrowser:value];
}
- (struct browser_window *)browser { return browser; }
- (Window *)nativeWindow { return window; }
#ifdef NETSURF_NEXTSTEP_QUALIFY
- (id)nativePlotView { return plotView; }
- (id)nativeLocationField { return urlBar; }
- (id)nativeReloadButton { return refreshButton; }
- (BOOL)nativeIsLoading { return [(Button *)refreshButton tag] != 0; }
#endif
- (void)displayBrowserIfNeeded
{
	if (nativeNeedsFullDisplay) {
		NSSize size = [self getBrowserSize];
		nativeNeedsFullDisplay = NO;
		if (browser) browser_window_reformat(browser, false, size.width, size.height);
		[self updateBrowserExtent];
		[window display];
	} else {
		[window displayIfNeeded];
	}
	[plotView displayPendingContent];
	[progressTrack displayPendingContent];
	[window flushWindow];
}
- (void)dealloc
{
	nextstep_misc_table.schedule(-1, finish_location_editing, self);
	[window setDelegate:nil];
	[window free];
	[nativeActionTarget free];
	[backImage free];
	[forwardImage free];
	[reloadImage free];
	[stopImage free];
	[super dealloc];
}
- windowWillClose:sender
{
	(void)sender;
	/* A core-initiated close already owns registry removal and release. */
	if (isClosing) return self;
	isClosing = YES;
	if (browser != NULL) browser_window_destroy(browser);
	else { [nextstep_browser_windows removeObject:self]; [self autorelease]; }
	return self;
}
- (void)netsurfWindowDestroy
{
	nextstep_misc_table.schedule(-1, finish_location_editing, self);
	browser = NULL;
	[plotView setBrowser:NULL];
	if (!isClosing) { isClosing = YES; [window close]; }
	/* The registry owns live controllers, the GUI callback owns the original
	 * allocation until this method returns. Window delegates never free self. */
	[nextstep_browser_windows removeObject:self];
	[self autorelease];
}
- (void)close:(id)sender
{
	(void)sender;
	if (browser) browser_window_destroy(browser);
	else [window close];
}
- windowDidResize:sender
{
	(void)sender;
	[self browserViewDidResize];
	return self;
}
- (void)browserViewDidResize
{
	NSSize size;
	if (scrollView == nil || plotView == nil) return;
	size = [self getBrowserSize];
	/* Native layout can revisit the hierarchy without changing its size.
	 * Reformat only when the actual browser viewport changed. */
	if (size.width == nativeViewportSize.width && size.height == nativeViewportSize.height)
		return;
	nativeViewportSize = size;
	/* Repositioning transparent controls invalidates their old background too.
	 * Repaint the hierarchy before the coalesced document pass. */
	[[window contentView] setNeedsDisplay:YES];
	nativeNeedsFullDisplay = YES;
	[self invalidateBrowser];
}
- (NSSize)getBrowserSize
{
	NSSize size = {0, 0};
	[scrollView getContentSize:&size];
	return size;
}
- (NSPoint)getBrowserScroll
{
	NXRect rect;
	[scrollView getDocVisibleRect:&rect];
	return rect.origin;
}
- (void)setBrowserScroll:(NSPoint)point
{
	[plotView scrollPoint:&point];
	[self invalidateBrowser];
}
- (void)invalidateBrowser { [plotView setNeedsDisplay:YES]; }
- (void)invalidateBrowser:(NSRect)rect
{
	(void)rect;
	/* Native invalidate:: concerns scrolling validity, not Cocoa-style dirty
	 * rectangles. Mark the view for drawing; optimize dirty regions later. */
	[plotView setNeedsDisplay:YES];
}
- (void)updateBrowserExtent
{
	int width, height;
	NSSize viewport;
	if (browser == NULL) return;
	viewport = [self getBrowserSize];
	browser_window_get_extents(browser, true, &width, &height);
	if (width < viewport.width) width = viewport.width;
	if (height < viewport.height) height = viewport.height;
	[plotView sizeTo:width :height];
}
- (void)placeCaretAtX:(int)x y:(int)y height:(int)height { [(NextstepPlotView *)plotView placeCaretAtX:x y:y height:height]; }
- (void)removeCaret { [(NextstepPlotView *)plotView removeCaret]; }
- (void)setPointerToShape:(enum gui_pointer_shape)shape
{
	if (shape == GUI_POINTER_CARET) [NXIBeam set]; else [NXArrow set];
}
- (void)newContent { [self removeCaret]; [NXArrow set]; }
- (void)setNavigationUrl:(NSString *)url
{
	/* A redirect or background load must not replace an address being typed. */
	if ([urlBar currentEditor] == nil) [urlBar setStringValue:[url cString]];
	[backButton setEnabled:browser && browser_window_back_available(browser)];
	[forwardButton setEnabled:browser && browser_window_forward_available(browser)];
}
- (void)setStatusText:(NSString *)text
{
	(void)text;
	if ([refreshButton tag] != 1) return;
	/* Activity estimate, not a byte-count percentage. Match the OPENSTEP UI. */
	if (openstepProgress < .15f) openstepProgress = .15f;
	else if (openstepProgress < .90f) {
		openstepProgress += .14f;
		if (openstepProgress > .90f) openstepProgress = .90f;
	}
	[progressTrack setProgress:openstepProgress];
}
- (void)setTitle:(NSString *)title { [(Window *)window setTitle:[title cString]]; }
- (void)startThrobber
{
	button_image(refreshButton, stopImage, "Stop");
	[refreshButton setTag:1];
	openstepProgress = .08f;
	[progressTrack setProgress:openstepProgress];
}
- (void)stopThrobber
{
	button_image(refreshButton, reloadImage, "Load");
	[refreshButton setTag:0];
	openstepProgress = 0;
	[progressTrack setProgress:0];
}
- (void)back:(id)sender { (void)sender; if (browser && browser_window_back_available(browser)) browser_window_history_back(browser, false); }
- (void)forward:(id)sender { (void)sender; if (browser && browser_window_forward_available(browser)) browser_window_history_forward(browser, false); }
- (void)reload:(id)sender { (void)sender; if (browser) browser_window_reload(browser, true); }
- (void)stopLoading:(id)sender { (void)sender; if (browser) browser_window_stop(browser); }
- (void)stopOrRefresh:(id)sender { if ([sender tag]) [self stopLoading:sender]; else [self reload:sender]; }
- (void)copy:(id)sender { [plotView copy:sender]; }
- (void)zoomIn:(id)sender { (void)sender; if (browser) browser_window_set_scale(browser, 0.05, false); }
- (void)zoomOut:(id)sender { (void)sender; if (browser) browser_window_set_scale(browser, -0.05, false); }
- (void)resetZoom:(id)sender { (void)sender; if (browser) browser_window_set_scale(browser, 1.0, true); }
- (NSString *)visibleUrl
{
	struct nsurl *url = browser ? browser_window_access_url(browser) : NULL;
	return url ? [NSString stringWithCString:nsurl_access(url)] : @"about:blank";
}
- (void)focusLocation:(id)sender
{
	(void)sender;
	[window makeKeyAndOrderFront:self];
	[urlBar selectText:self];
}
- (void)enterUrl:(id)sender
{
	NSString *address;
	[sender validateEditing];
	address = [NSString stringWithCString:[sender stringValue]];
	[self openUrlString:address];
	/* TextField finishes its own responder changes after sending the action.
	 * Hand focus back only after that native editing operation has unwound. */
	if (nextstep_misc_table.schedule(0, finish_location_editing, self) != NSERROR_OK)
		[window makeFirstResponder:plotView];
}
- (void)finishLocationEditing
{
	if (!isClosing) [window makeFirstResponder:plotView];
}
- (void)openUrlString:(NSString *)text
{
	struct nsurl *url;
	nserror error;
	NSString *address = text;
	if ([text rangeOfString:@":"].location == NSNotFound)
		address = [NSString stringWithFormat:@"http://%@", text];
	NSData *utf8 = nextstep_utf8_data(address);
	char *bytes;
	if (utf8 == nil) return;
	bytes = malloc([utf8 length] + 1);
	if (bytes == NULL) return;
	memcpy(bytes, [utf8 bytes], [utf8 length]);
	bytes[[utf8 length]] = '\0';
	error = nsurl_create(bytes, &url);
	free(bytes);
	if (error != NSERROR_OK) return;
	if (browser == NULL) {
		pending_target = self;
		error = browser_window_create(BW_CREATE_HISTORY, url, NULL, NULL, NULL);
		pending_target = nil;
	} else {
		error = browser_window_navigate(browser, url, NULL, BW_NAVIGATE_HISTORY,
			NULL, NULL, NULL);
	}
	nsurl_unref(url);
	if (error != NSERROR_OK) NSLOG(netsurf, WARNING, "Navigation failed: %d", error);
}
/* NEXTSTEP uses NetSurf's in-page select menus (core_select_menu). */
- (void)showDropdownMenuWithOptions:(NSArray *)options atLocation:(NSPoint)location control:(struct form_control *)control
{
	(void)options; (void)location; (void)control;
	NSLOG(netsurf, WARNING, "Native select menu requested despite core_select_menu");
}
@end

/* Coalesce core invalidations after an event or DPS timed callback. Old AppKit
 * may not traverse buffered windows when only a document subview is dirty. */
void nextstep_display_windows(void)
{
	unsigned i;
	for (i = 0; i < [nextstep_browser_windows count]; i++)
		[[nextstep_browser_windows objectAtIndex:i] displayBrowserIfNeeded];
}
