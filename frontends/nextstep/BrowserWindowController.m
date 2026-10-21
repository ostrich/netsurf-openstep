/* SPDX-License-Identifier: GPL-2.0-or-later */
#import "../openstep/BrowserWindowController.h"
#import "PlotView.h"
#import "text.h"
#import <appkit/NXCursor.h>
#import <appkit/ClipView.h>
#include "netsurf/browser_window.h"
#include "netsurf/keypress.h"
#include "desktop/browser_history.h"
#include "utils/nsurl.h"
#include "utils/log.h"

static id pending_target;
NSMutableArray *nextstep_browser_windows;

static Button *button(View *parent, id target, const char *title, SEL action,
		float x, float width)
{
	NXRect rect = NSMakeRect(x, 6, width, 28);
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
		if (nextstep_browser_windows == nil)
			nextstep_browser_windows = [NSMutableArray new];
		[nextstep_browser_windows addObject:self];
	}
	return self;
}
- (void)loadWindow
{
	NXRect rect = NSMakeRect(60, 60, 720, 480);
	View *content, *toolbar;
	if (window != nil) return;
	window = [[Window alloc] initContent:&rect style:NX_RESIZEBARSTYLE
		backing:NX_BUFFERED buttonMask:NX_CLOSEBUTTONMASK | NX_MINIATURIZEBUTTONMASK
		defer:NO];
	[(Window *)window setTitle:"NetSurf"];
	[window setFreeWhenClosed:NO];
	[window setDelegate:self];
	[window addToEventMask:NX_MOUSEMOVEDMASK];
	content = [window contentView];
	rect = NSMakeRect(0, 440, 720, 40);
	toolbar = [[View alloc] initFrame:&rect];
	[toolbar setAutoresizeSubviews:YES];
	[toolbar setAutosizing:NX_WIDTHSIZABLE | NX_MINYMARGINSIZABLE];
	[content addSubview:toolbar];
	backButton = button(toolbar, self, "Back", @selector(back:), 6, 50);
	forwardButton = button(toolbar, self, "Forward", @selector(forward:), 60, 66);
	refreshButton = button(toolbar, self, "Reload", @selector(stopOrRefresh:), 130, 62);
	rect = NSMakeRect(198, 9, 516, 22);
	urlBar = [[TextField alloc] initFrame:&rect];
	[urlBar setBezeled:YES];
	[urlBar setEditable:YES];
	[urlBar setSelectable:YES];
	[urlBar setTarget:self];
	[urlBar setAction:@selector(enterUrl:)];
	[urlBar setAutosizing:NX_WIDTHSIZABLE];
	[toolbar addSubview:urlBar];
	rect = NSMakeRect(0, 0, 720, 440);
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
- (void)displayBrowserIfNeeded
{
	[plotView displayPendingContent];
	[window displayIfNeeded];
	[window flushWindow];
}
- (void)dealloc
{
	[window setDelegate:nil];
	[window free];
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
	NSSize size = [self getBrowserSize];
	(void)sender;
	if (browser) browser_window_reformat(browser, false, size.width, size.height);
	[self updateBrowserExtent];
	return self;
}
- (NSSize)getBrowserSize
{
	NSSize size;
	[scrollView getContentSize:&size];
	return size;
}
- (NSPoint)getBrowserScroll
{
	NXRect rect;
	[scrollView getDocVisibleRect:&rect];
	return rect.origin;
}
- (void)setBrowserScroll:(NSPoint)point { [plotView scrollPoint:&point]; }
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
	[urlBar setStringValue:[url cString]];
	[backButton setEnabled:browser && browser_window_back_available(browser)];
	[forwardButton setEnabled:browser && browser_window_forward_available(browser)];
}
- (void)setStatusText:(NSString *)text { (void)text; }
- (void)setTitle:(NSString *)title { [(Window *)window setTitle:[title cString]]; }
- (void)startThrobber { [(Button *)refreshButton setTitle:"Stop"]; [refreshButton setTag:1]; }
- (void)stopThrobber { [(Button *)refreshButton setTitle:"Reload"]; [refreshButton setTag:0]; }
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
- (void)enterUrl:(id)sender { [self openUrlString:[NSString stringWithCString:[sender stringValue]]]; }
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
