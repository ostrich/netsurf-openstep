/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Opt-in integration test, excluded from ordinary application builds. */
#import "platform.h"
#import "../openstep/BrowserWindowController.h"
#import "PlotView.h"
#include <stdio.h>
#include <string.h>
#include "netsurf/browser_window.h"
#include "netsurf/clipboard.h"
#include "netsurf/keypress.h"
#include "content/content.h"

extern NSMutableArray *nextstep_browser_windows;
extern struct gui_clipboard_table nextstep_clipboard_table;
@interface BrowserWindowController (Qualification)
- (Window *)nativeWindow;
- (id)nativePlotView;
@end
static BrowserWindowController *primary, *secondary;
static FILE *results;
static NSString *first_url, *second_url, *http_url, *https_url;
static unsigned stage;
static double began, changed;
static DPSTimedEntry entry;
static int failures;
static BOOL ticking;
static NSSize before_resize;

static void check(const char *label, BOOL ok)
{
	fprintf(results, "GUI %s %s\n", ok ? "PASS" : "FAIL", label);
	fflush(results);
	if (!ok) failures++;
}
static BOOL ready(BrowserWindowController *controller, const char *title)
{
	struct browser_window *browser = [controller browser];
	struct hlcache_handle *content = browser ? browser_window_get_content(browser) : NULL;
	return content != NULL && content_get_status(content) == CONTENT_STATUS_DONE &&
		strcmp(browser_window_get_title(browser), title) == 0;
}
static BOOL clipboard_contains(const char *expected)
{
	char *data;
	size_t length;
	BOOL found;
	nextstep_clipboard_table.get(&data, &length);
	found = data != NULL && strstr(data, expected) != NULL;
	free(data);
	return found;
}
static void click(id view, float x, float y)
{
	NXEvent event;
	memset(&event, 0, sizeof(event));
	event.location = NSMakePoint(x, y);
	[view convertPoint:&event.location toView:nil];
	event.type = NX_LMOUSEDOWN;
	event.data.mouse.click = 1;
	[view mouseDown:&event];
	event.type = NX_LMOUSEUP;
	[view mouseUp:&event];
}
static void finish(void)
{
	if (entry) DPSRemoveTimedEntry(entry);
	entry = NULL;
	fprintf(results, "GUI-SUITE %d\n", failures);
	fclose(results);
	results = NULL;
	[NXApp terminate:nil];
}
static void tick(DPSTimedEntry timer, double now, void *context)
{
	NSAutoreleasePool *pool;
	struct browser_window *browser;
	/* Window resizing and focus operations can pump nested DPS callbacks. */
	if (ticking) return;
	ticking = YES;
	/* Retire the timer before native calls which can run nested DPS loops.
	 * Leaving an overdue repeating timer active can starve those loops. */
	DPSRemoveTimedEntry(timer);
	entry = NULL;
	pool = [NSAutoreleasePool new];
	browser = [primary browser];
	(void)timer; (void)context;
	if (began == 0) began = changed = now;
	if (now - began > 180 || now - changed > 45) {
		check("stage-deadline", NO);
		fprintf(results, "GUI-STAGE %u\n", stage);
		finish();
		[pool release];
		ticking = NO;
		return;
	}
	switch (stage) {
	case 0:
		if (!ready(primary, "Native browser check")) break;
		browser_window_key_press(browser, NS_KEY_SELECT_ALL);
		browser_window_key_press(browser, NS_KEY_COPY_SELECTION);
		check("DOM-JavaScript-and-native-clipboard", clipboard_contains("JavaScript works"));
		check("document-extents", ({int w, h; browser_window_get_extents(browser, true, &w, &h); w > 0 && h >= 1200;}));
		stage++; changed = now;
		break;
	case 1:
		/* Leave the rendered fixture visible for host screenshot collection. */
		if (now - changed < 10) break;
		{
			NXEvent key;
			id view = [primary nativePlotView];
			click(view, 35, 160);
			memset(&key, 0, sizeof(key));
			key.type = NX_KEYDOWN; key.data.key.charCode = 'q';
			[view keyDown:&key];
			browser_window_key_press(browser, NS_KEY_SELECT_ALL);
			browser_window_key_press(browser, NS_KEY_COPY_SELECTION);
			check("form-mouse-keyboard-copy", clipboard_contains("q"));
			click(view, 30, 250);
		}
		{
			NSSize before = [primary getBrowserSize];
			before_resize = before;
			[[primary nativeWindow] sizeWindow:before.width - 40 :before.height - 20];
			[primary setBrowserScroll:NSMakePoint(0, 300)];
			check("document-scroll", [primary getBrowserScroll].y >= 299);
			[primary setBrowserScroll:NSMakePoint(0, 0)];
			check("document-scroll-reset", [primary getBrowserScroll].y == 0);
		}
		secondary = [[BrowserWindowController alloc] initWithBrowser:NULL];
		[secondary loadWindow];
		[secondary openUrlString:second_url];
		stage++; changed = now;
		break;
	case 2:
		if (!ready(secondary, "Second page")) break;
		{
			NSSize after = [primary getBrowserSize];
			check("native-window-resize", before_resize.width != after.width && after.width > 0 && after.height > 0);
		}
		check("second-window-load", [nextstep_browser_windows count] == 2);
		[secondary close:nil]; secondary = nil;
		check("second-window-close", [nextstep_browser_windows count] == 1);
		[primary openUrlString:second_url];
		stage++; changed = now;
		break;
	case 3:
		if (!ready(primary, "Second page")) break;
		check("same-window-navigation", YES);
		[primary back:nil]; stage++; changed = now;
		break;
	case 4:
		if (!ready(primary, "Native browser check")) break;
		check("history-back", YES);
		[primary forward:nil]; stage++; changed = now;
		break;
	case 5:
		if (!ready(primary, "Second page")) break;
		check("history-forward", YES);
		[primary openUrlString:http_url]; stage++; changed = now;
		break;
	case 6:
		if (!ready(primary, "Network browser check")) break;
		browser_window_key_press(browser, NS_KEY_SELECT_ALL);
		browser_window_key_press(browser, NS_KEY_COPY_SELECTION);
		check("HTTP-fetch-and-JavaScript", clipboard_contains("JavaScript works"));
		[primary openUrlString:https_url]; stage++; changed = now;
		break;
	case 7:
		if (!ready(primary, "Secure browser check")) break;
		browser_window_key_press(browser, NS_KEY_SELECT_ALL);
		browser_window_key_press(browser, NS_KEY_COPY_SELECTION);
		check("verified-HTTPS-fetch", clipboard_contains("JavaScript works"));
		[primary reload:nil]; stage++; changed = now;
		break;
	case 8:
		if (now - changed < 1 || !ready(primary, "Secure browser check")) break;
		check("reload-completes", YES);
		[primary close:nil]; primary = nil;
		check("last-window-close", [nextstep_browser_windows count] == 0);
		primary = [[BrowserWindowController alloc] initWithBrowser:NULL];
		[primary loadWindow];
		[primary openUrlString:second_url];
		stage++; changed = now;
		break;
	case 9:
		if (!ready(primary, "Second page")) break;
		check("reopen-after-last-window", [nextstep_browser_windows count] == 1);
		finish();
		break;
	}
	nextstep_display_windows();
	[pool release];
	ticking = NO;
	if (results) entry = DPSAddTimedEntry(.1, tick, NULL, NX_MODALRESPTHRESHOLD);
}
void nextstep_qualification_start(const char *directory)
{
	char path[4096], http[512], https[512];
	FILE *config;
	if (strlen(directory) > 4000) exit(64);
	sprintf(path, "%s/gui-results.txt", directory);
	results = fopen(path, "w");
	if (results == NULL) exit(65);
	sprintf(path, "%s/urls.txt", directory);
	config = fopen(path, "r");
	if (!config || fscanf(config, "%511s %511s", http, https) != 2) exit(66);
	fclose(config);
	first_url = [[NSString stringWithFormat:@"file://%s/fixture.html", directory] retain];
	second_url = [[NSString stringWithFormat:@"file://%s/second.html", directory] retain];
	http_url = [[NSString stringWithCString:http] retain];
	https_url = [[NSString stringWithCString:https] retain];
	primary = [nextstep_browser_windows objectAtIndex:0];
	[primary openUrlString:first_url];
	entry = DPSAddTimedEntry(.1, tick, NULL, NX_MODALRESPTHRESHOLD);
	if (!entry) exit(67);
}
