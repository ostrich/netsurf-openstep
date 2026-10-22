/* SPDX-License-Identifier: GPL-2.0-or-later */
#import "platform.h"
#import "schedule.h"
#import "../openstep/BrowserWindowController.h"
#import "../openstep/tables/tables.h"
#import <appkit/Cell.h>
#import <appkit/Matrix.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include "netsurf/netsurf.h"
#include "netsurf/browser_window.h"
#include "netsurf/plot_style.h"
#include "utils/nsoption.h"
#include "utils/nsurl.h"
#include "utils/log.h"
#include "framebuffer/bitmap.h"
#include "framebuffer/font.h"
#include "framebuffer/findfile.h"

extern NSMutableArray *nextstep_browser_windows;
extern struct gui_clipboard_table nextstep_clipboard_table;
static NSString *initial_url;
static BOOL startup_trace;
#define TRACE(message) do { if (startup_trace) { fprintf(stderr, "NetSurf: %s\n", message); fflush(stderr); } } while (0)
extern int nextstep_smoke_test(void);
#ifdef NETSURF_NEXTSTEP_QUALIFY
extern void nextstep_qualification_start(const char *directory);
extern void nextstep_everyday_start(const char *directory);
#endif

static nserror defaults(struct nsoption_s *options)
{
	NSString *ca = [[NSBundle mainBundle] pathForResource:@"ca-bundle" ofType:@""];
	char *path;
	if (ca == nil) return NSERROR_NOT_FOUND;
	path = malloc(strlen([ca cString]) + 1);
	if (path == NULL) return NSERROR_NOMEM;
	strcpy(path, [ca cString]);
	nsoption_setnull_charp(ca_bundle, path);
	options[NSOPTION_enable_javascript].value.b = true;
	options[NSOPTION_core_select_menu].value.b = true;
	options[NSOPTION_font_default].value.i = PLOT_FONT_FAMILY_SERIF;
	options[NSOPTION_font_size].value.i = 105;
	options[NSOPTION_font_min_size].value.i = 70;
	options[NSOPTION_max_fetchers].value.i = 8;
	options[NSOPTION_max_fetchers_per_host].value.i = 2;
	options[NSOPTION_max_cached_fetch_handles].value.i = 2;
	return NSERROR_OK;
}

@interface NextstepApplication : Application
@end
@interface BrowserWindowController (NativeWindow)
- (Window *)nativeWindow;
- (void)displayBrowserIfNeeded;
- (void)focusLocation:(id)sender;
@end

@implementation NextstepApplication
- updateWindows
{
	[super updateWindows];
	nextstep_display_windows();
	return self;
}
- sendEvent:(NXEvent *)event
{
	NSAutoreleasePool *pool = [NSAutoreleasePool new];
	[super sendEvent:event];
	[pool release];
	return self;
}
@end

static BrowserWindowController *front_browser(void)
{
	unsigned i;
	Window *key = [NXApp keyWindow];
	for (i = 0; i < [nextstep_browser_windows count]; i++) {
		BrowserWindowController *candidate = [nextstep_browser_windows objectAtIndex:i];
		if ([candidate nativeWindow] == key) return candidate;
	}
	return nil;
}

@interface NextstepDelegate : Object { BOOL started; }
- newWindow:sender;
@end
@implementation NextstepDelegate
- appDidInit:sender
{
	(void)sender;
	if (started) return self;
	started = YES;
	TRACE("creating first browser window");
	[self newWindow:nil];
	TRACE("first browser window created");
	return self;
}
- newWindow:sender
{
	BrowserWindowController *controller;
	(void)sender;
	controller = [[BrowserWindowController alloc] initWithBrowser:NULL];
	[controller loadWindow];
	[controller openUrlString:initial_url ? initial_url : @"about:welcome"];
	return self;
}
- back:sender { [front_browser() back:sender]; return self; }
- focusLocation:sender { [front_browser() focusLocation:sender]; return self; }
- forward:sender { [front_browser() forward:sender]; return self; }
- reload:sender { [front_browser() reload:sender]; return self; }
- stopLoading:sender { [front_browser() stopLoading:sender]; return self; }
- zoomIn:sender { [front_browser() zoomIn:sender]; return self; }
- zoomOut:sender { [front_browser() zoomOut:sender]; return self; }
- resetZoom:sender { [front_browser() resetZoom:sender]; return self; }
- appWillTerminate:sender
{
	(void)sender;
	while ([nextstep_browser_windows count])
		[[nextstep_browser_windows objectAtIndex:0] close:nil];
	nextstep_schedule_shutdown();
	fb_font_finalise();
	netsurf_exit();
	return self;
}
@end

static void add_item(Menu *menu, const char *title, SEL action,
		unsigned short key, id target)
{
	id cell = [menu addItem:title action:action keyEquivalent:key];
	[cell setTarget:target];
}

static int failed(const char *step, int error)
{
	fprintf(stderr, "NetSurf: %s failed (%d)\n", step, error);
	return 1;
}

int main(int argc, char **argv)
{
	NSAutoreleasePool *pool = [NSAutoreleasePool new];
	NextstepApplication *app;
	NextstepDelegate *delegate;
	Menu *menu;
	NSString *font_path, *prefs;
	nserror error;
	BOOL smoke = argc == 2 && strcmp(argv[1], "--smoke-test") == 0;
	struct netsurf_table table = {
		.misc = &nextstep_misc_table,
		.window = &openstep_window_table,
		.clipboard = &nextstep_clipboard_table,
		.fetch = &openstep_fetch_table,
		.bitmap = framebuffer_bitmap_table,
		.layout = framebuffer_layout_table,
		.utf8 = framebuffer_utf8_table
	};
	startup_trace = getenv("NETSURF_STARTUP_TRACE") != NULL;
	/* Establish AppKit's desktop context before starting core DPS timers. */
	if (!smoke) {
		TRACE("creating Application");
		app = [NextstepApplication new];
		if (app == nil) return failed("Application initialization", 1);
		TRACE("Application created");
	}
	TRACE("initializing browser core");
	nslog_init(NULL, &argc, argv);
	error = netsurf_register(&table);
	if (error != NSERROR_OK) return failed("callback registration", error);
	error = nsoption_init(defaults, &nsoptions, &nsoptions_default);
	if (error != NSERROR_OK) return failed("default options", error);
	prefs = [@"~/.config/NetSurf/prefs" stringByExpandingTildeInPath];
	nsoption_read([prefs cString], nsoptions);
	/* A preference copied from OPENSTEP must not request an unavailable native
	 * select popup. The browser's core popup is supported on both systems. */
	nsoption_set_bool(core_select_menu, true);
	font_path = [[[NSBundle mainBundle] bundlePath]
		stringByAppendingPathComponent:@"Resources/Fonts"];
	respaths = fb_init_resource_path([font_path cString]);
	if (respaths == NULL) return failed("font resource paths", NSERROR_NOMEM);
	error = netsurf_init(NULL);
	if (error != NSERROR_OK) return failed("browser initialization", error);
	if (!fb_font_init()) return failed("font initialization", 1);
	if (smoke) {
		int status = nextstep_smoke_test();
		nextstep_schedule_shutdown();
		fb_font_finalise();
		netsurf_exit();
		[pool release];
		return status;
	}
	/* Workspace supplies -NX... defaults as argument pairs. They are not
	 * navigation URLs; AppKit still consumes them from the process arguments. */
	{
		int i;
		for (i = 1; i < argc; i++) {
			if (strncmp(argv[i], "-NX", 3) == 0) { if (i + 1 < argc) i++; continue; }
			if (strncmp(argv[i], "http:", 5) == 0 || strncmp(argv[i], "https:", 6) == 0 ||
				strncmp(argv[i], "file:", 5) == 0 || strncmp(argv[i], "about:", 6) == 0) {
				initial_url = [[NSString stringWithCString:argv[i]] retain];
				break;
			}
		}
	}
	delegate = [NextstepDelegate new];
	[app setDelegate:delegate];
	menu = [[Menu alloc] initTitle:"NetSurf"];
	add_item(menu, "New window", @selector(newWindow:), 'n', delegate);
	add_item(menu, "Close", @selector(performClose:), 'w', nil);
	add_item(menu, "Open location...", @selector(focusLocation:), 'l', delegate);
	add_item(menu, "Cut", @selector(cut:), 'x', nil);
	add_item(menu, "Copy", @selector(copy:), 'c', nil);
	add_item(menu, "Paste", @selector(paste:), 'v', nil);
	add_item(menu, "Select all", @selector(selectAll:), 'a', nil);
	add_item(menu, "Back", @selector(back:), '[', delegate);
	add_item(menu, "Forward", @selector(forward:), ']', delegate);
	add_item(menu, "Reload", @selector(reload:), 'r', delegate);
	add_item(menu, "Stop", @selector(stopLoading:), '.', delegate);
	add_item(menu, "Zoom in", @selector(zoomIn:), '+', delegate);
	add_item(menu, "Zoom out", @selector(zoomOut:), '-', delegate);
	add_item(menu, "Actual size", @selector(resetZoom:), '0', delegate);
	add_item(menu, "Hide", @selector(hide:), 'h', app);
	add_item(menu, "Quit", @selector(terminate:), 'q', app);
	[menu sizeToFit];
	[app setMainMenu:menu];
	[delegate appDidInit:app];
#ifdef NETSURF_NEXTSTEP_QUALIFY
	{
		int i;
		for (i = 1; i + 1 < argc; i++)
			if (strcmp(argv[i], "--qualification") == 0)
				nextstep_qualification_start(argv[i + 1]);
			else if (strcmp(argv[i], "--everyday") == 0)
				nextstep_everyday_start(argv[i + 1]);
	}
#endif
	[app activateSelf:YES];
	TRACE("entering event loop");
	[app run];
	[initial_url release];
	[pool release];
	return 0;
}
