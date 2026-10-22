/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Opt-in native event-queue acceptance test, never linked into release builds. */
#import "platform.h"
#import "../openstep/BrowserWindowController.h"
#import "PlotView.h"
#import "../openstep/FrameBufferRenderer.h"
#include <stdio.h>
#include <string.h>
#include "netsurf/browser_window.h"
#include "netsurf/clipboard.h"
#include "netsurf/keypress.h"
#include "content/content.h"

extern NSMutableArray *nextstep_browser_windows;
extern struct gui_clipboard_table nextstep_clipboard_table;
@interface BrowserWindowController (Everyday)
- (Window *)nativeWindow;
- (id)nativePlotView;
- (id)nativeLocationField;
- (id)nativeReloadButton;
- (BOOL)nativeIsLoading;
@end
static BrowserWindowController *controller;
static FILE *report;
static NSString *fixture;
static unsigned step;
static int failures;
static double started, changed;
static BOOL busy;
static DPSTimedEntry timer;
static NXRect original;
static float scroll_before;
static short mouse_sequence;
static unsigned paint_step;
static double paint_began;
static struct hlcache_handle *before_reload;
static struct hlcache_handle *before_navigation;

static void check(const char *name, BOOL passed)
{
	fprintf(report, "EVERYDAY %s %s\n", passed ? "PASS" : "FAIL", name);
	fflush(report);
	if (!passed) failures++;
}
static BOOL ready(const char *title)
{
	struct browser_window *bw = [controller browser];
	struct hlcache_handle *content = browser_window_get_content(bw);
	return content && ![controller nativeIsLoading] &&
		content_get_status(content) == CONTENT_STATUS_DONE &&
		!strcmp(browser_window_get_title(bw), title);
}
static void key(unsigned code, unsigned flags, unsigned charset)
{
	NXEvent e;
	memset(&e, 0, sizeof(e));
	e.window = [[controller nativeWindow] windowNum];
	e.ctxt = DPSGetCurrentContext();
	e.flags = flags;
	e.data.key.charSet = charset;
	e.data.key.charCode = code;
	if (code == '\r') e.data.key.keyCode = 0x2a;
	e.type = NX_KEYDOWN;
	DPSPostEvent(&e, 0);
	e.type = NX_KEYUP;
	DPSPostEvent(&e, 0);
}
static void text(const char *value)
{
	while (*value) key((unsigned char)*value++, 0, NX_ASCIISET);
}
static void click(float x, float y)
{
	NXEvent e;
	memset(&e, 0, sizeof(e));
	e.location = NSMakePoint(x, y);
	[[controller nativePlotView] convertPoint:&e.location toView:nil];
	e.window = [[controller nativeWindow] windowNum];
	e.ctxt = DPSGetCurrentContext();
	e.data.mouse.click = 1;
	e.data.mouse.eventNum = ++mouse_sequence;
	e.type = NX_LMOUSEDOWN;
	[[controller nativeWindow] sendEvent:&e];
	e.type = NX_LMOUSEUP;
	[[controller nativeWindow] sendEvent:&e];
}
static void drag_selection(BOOL finish_drag)
{
	NXEvent e;
	memset(&e, 0, sizeof(e));
	e.location = finish_drag ? NSMakePoint(240, 310) : NSMakePoint(22, 310);
	[[controller nativePlotView] convertPoint:&e.location toView:nil];
	e.window = [[controller nativeWindow] windowNum];
	e.ctxt = DPSGetCurrentContext();
	e.data.mouse.click = 1;
	if (!finish_drag) mouse_sequence++;
	e.data.mouse.eventNum = mouse_sequence;
	e.type = finish_drag ? NX_LMOUSEDRAGGED : NX_LMOUSEDOWN;
	/* Test this view's selection implementation directly. These synthetic
	 * events do not establish reliable WindowServer drag-tracking state after
	 * a native Button click. Other click checks above use Window hit testing;
	 * this callback-level check has narrower scope. */
	if (finish_drag) {
		[[controller nativePlotView] mouseDragged:&e];
		e.type = NX_LMOUSEUP;
		[[controller nativePlotView] mouseUp:&e];
	} else {
		[[controller nativePlotView] mouseDown:&e];
	}
}
static void click_reload(void)
{
	/* Native Control's click API drives target/action without inventing
	 * WindowServer button-tracking state for a synthetic mouse press. */
	[[controller nativeReloadButton] performClick:nil];
}
static void pasteboard(const char *value)
{
	nextstep_clipboard_table.set(value, strlen(value), NULL, 0);
}
static BOOL copied(const char *expected)
{
	char *value = NULL;
	size_t length = 0;
	BOOL equal;
	nextstep_clipboard_table.get(&value, &length);
	equal = value && length == strlen(expected) && !memcmp(value, expected, length);
	fprintf(report, "COPIED expected=%s actual=%s\n", expected, value ? value : "(null)");
	free(value);
	return equal;
}
static BOOL copied_selection(void)
{
	char *value = NULL;
	size_t length = 0;
	BOOL found;
	nextstep_clipboard_table.get(&value, &length);
	fprintf(report, "SELECTION %lu %s\n", (unsigned long)length, value ? value : "(null)");
	found = value && strstr(value, "Selection") != NULL;
	free(value);
	return found;
}
static void finish(void)
{
	fprintf(report, "EVERYDAY-SUITE %d\n", failures);
	fclose(report);
	report = NULL;
	[NXApp terminate:nil];
}
static void tick(DPSTimedEntry entry, double now, void *context)
{
	NSAutoreleasePool *pool;
	Window *window = [controller nativeWindow];
	if (busy) return;
	busy = YES;
	DPSRemoveTimedEntry(entry);
	timer = NULL;
	pool = [NSAutoreleasePool new];
	(void)context;
	if (!started) started = changed = now;
	if (step >= 15 && step <= 18) {
		const char *titles[] = {"Paint deep", "Paint shrunk", "Paint restored", "Paint reference"};
		[window setTitle:titles[step - 15]];
		if (paint_step != step) { paint_step = step; paint_began = now; }
	}
	if (now - started > 240 || now - changed > 40) {
		check("deadline", NO);
		fprintf(report, "EVERYDAY-STAGE %u\n", step);
		finish();
	} else if (now - changed >= 1) {
		switch (step) {
		case 0:
			if (!ready("Everyday controls")) break;
			[[window contentView] getBounds:&original];
			fprintf(report, "ROOT-NATIVE-PERFORM %d RESPONDS %d\n",
				[controller respondsToSelector:@selector(perform:with:)],
				[controller respondsToSelector:@selector(respondsTo:)]);
			key('l', NX_COMMANDMASK, NX_ASCIISET);
			step++; changed = now; break;
		case 1:
			if ([[controller nativeLocationField] currentEditor] == nil) break;
			check("command-L-location-editor", YES);
			pasteboard([fixture cString]);
			key('v', NX_COMMANDMASK, NX_ASCIISET);
			key(0xae, 0, NX_SYMBOLSET);
			text("#");
			key('a', NX_COMMANDMASK, NX_ASCIISET); key('c', NX_COMMANDMASK, NX_ASCIISET);
			step++; changed = now; break;
		case 2:
			if (!copied([[NSString stringWithFormat:@"%@#", fixture] cString])) break;
			check("native-location-paste", YES);
			before_navigation = browser_window_get_content([controller browser]);
			key('\r', 0, NX_ASCIISET);
			step++; changed = now; break;
		case 3:
			if (!ready("Everyday controls") ||
				browser_window_get_content([controller browser]) == before_navigation) break;
			fprintf(report, "FOCUS first=%p editor=%p plot=%p\n", [window firstResponder],
				[[controller nativeLocationField] currentEditor], [controller nativePlotView]);
			check("return-focuses-document", [window firstResponder] == [controller nativePlotView]);
			click(35, 160);
			text("abx"); key(0x7f, 0, NX_ASCIISET); text("c");
			key('a', NX_COMMANDMASK, NX_ASCIISET); key('c', NX_COMMANDMASK, NX_ASCIISET);
			step++; changed = now; break;
		case 4:
			if (!copied("abc")) break;
			check("queued-mouse-type-backspace-copy", YES);
			pasteboard("pasted value"); key('v', NX_COMMANDMASK, NX_ASCIISET);
			key('a', NX_COMMANDMASK, NX_ASCIISET); key('x', NX_COMMANDMASK, NX_ASCIISET);
			step++; changed = now; break;
		case 5:
			if (!copied("pasted value")) break;
			check("native-paste-and-cut", YES);
			text("typed"); key('\t', 0, NX_ASCIISET); text("second");
			key('a', NX_COMMANDMASK, NX_ASCIISET); key('c', NX_COMMANDMASK, NX_ASCIISET);
			step++; changed = now; break;
		case 6:
			if (!copied("second")) break;
			check("form-tab-focus", YES);
			key(0x19, NX_SHIFTMASK, NX_ASCIISET);
			key('a', NX_COMMANDMASK, NX_ASCIISET); key('c', NX_COMMANDMASK, NX_ASCIISET);
			step++; changed = now; break;
		case 7:
			if (!copied("typed")) break;
			check("form-shift-tab-focus", YES);
			click(35, 250);
			step++; changed = now; break;
		case 8:
			if (!ready("Second page")) break;
			check("queued-link-click", YES);
			key('[', NX_COMMANDMASK, NX_ASCIISET);
			step++; changed = now; break;
		case 9:
			if (!ready("Everyday controls")) break;
			check("command-history-back", YES);
			key(']', NX_COMMANDMASK, NX_ASCIISET);
			step++; changed = now; break;
		case 10:
			if (!ready("Second page")) break;
			check("command-history-forward", YES);
			key('[', NX_COMMANDMASK, NX_ASCIISET);
			step++; changed = now; break;
		case 11:
			if (!ready("Everyday controls")) break;
			[controller setBrowserScroll:NSMakePoint(0, 0)];
			click(30, 25);
			key(0xaf, 0, NX_SYMBOLSET);
			step++; changed = now; break;
		case 12:
			if ([controller getBrowserScroll].y <= 0) break;
			check("arrow-scroll", YES);
			scroll_before = [controller getBrowserScroll].y;
			key(' ', 0, NX_ASCIISET);
			step++; changed = now; break;
		case 13:
			if ([controller getBrowserScroll].y <= scroll_before + 100) break;
			check("space-page-scroll", YES);
			scroll_before = [controller getBrowserScroll].y;
			key(' ', NX_SHIFTMASK, NX_ASCIISET);
			step++; changed = now; break;
		case 14:
			if ([controller getBrowserScroll].y >= scroll_before) break;
			check("shift-space-page-scroll", YES);
			[controller setBrowserScroll:NSMakePoint(0, 19000)];
			[window setTitle:"Paint deep"];
			step++; changed = now; break;
		case 15:
			if (now - paint_began < 8) break;
			check("deep-scroll", [controller getBrowserScroll].y >= 18999);
			{
				NSSize surface = nextstep_framebuffer_test_size();
				NSSize viewport = [controller getBrowserSize];
				check("viewport-sized-framebuffer", surface.width > 0 && surface.height > 0 &&
					surface.width <= viewport.width + 2 && surface.height <= viewport.height + 2);
				fprintf(report, "FRAMEBUFFER %g %g VIEWPORT %g %g\n",
					surface.width, surface.height, viewport.width, viewport.height);
			}
			[controller setBrowserScroll:NSMakePoint(0, 0)];
			[window sizeWindow:480 :340];
			[window setTitle:"Paint shrunk"];
			step++; changed = now; break;
		case 16:
			if (now - paint_began < 8) break;
			check("resized-viewport", [controller getBrowserSize].width > 100 && [controller getBrowserSize].width < 500);
			[window sizeWindow:original.size.width :original.size.height];
			[window setTitle:"Paint restored"];
			step++; changed = now; break;
		case 17:
			if (now - paint_began < 8) break;
			[window display];
			[window setTitle:"Paint reference"];
			step++; changed = now; break;
		case 18:
			if (now - paint_began < 8) break;
			check("window-remains-responsive", [window firstResponder] == [controller nativePlotView]);
			before_reload = browser_window_get_content([controller browser]);
			[window setTitle:"Reload check"];
			click_reload();
			step++; changed = now; break;
		case 19:
			if (!ready("Everyday controls") ||
				browser_window_get_content([controller browser]) == before_reload) break;
			check("native-reload-button", YES);
			drag_selection(NO);
			step++; changed = now; break;
		case 20:
			drag_selection(YES);
			key('c', NX_COMMANDMASK, NX_ASCIISET);
			step++; changed = now; break;
		case 21:
			if (!copied_selection()) break;
			check("view-drag-selection-copy", YES);
			[window setTitle:"Host keyboard"];
			step++; changed = now; break;
		case 22:
			/* The host monitor now sends actual SDL keyboard input, separately
			 * from the application's event-queue tests above. */
			if ([[controller nativeLocationField] currentEditor] == nil) break;
			if (!copied("host-route")) break;
			check("host-keyboard-location-and-type", YES);
			[[controller nativeLocationField] abortEditing];
			[window makeFirstResponder:[controller nativePlotView]];
			step++; changed = now; break;
		case 23:
			/* Let the native field-editor tracking stack unwind before freeing
			 * its window from a later acceptance-test callback. */
			if ([[controller nativeLocationField] currentEditor] != nil) break;
			{
				BrowserWindowController *other = [[BrowserWindowController alloc] initWithBrowser:NULL];
				[other loadWindow];
				[other openUrlString:fixture];
				[[other nativeWindow] performClose:nil];
				check("native-close-during-load", [nextstep_browser_windows count] == 1);
			}
			[window performClose:nil];
			check("native-close-last-window", [nextstep_browser_windows count] == 0);
			finish(); break;
		}
	}
	nextstep_display_windows();
	[pool release];
	busy = NO;
	if (report) timer = DPSAddTimedEntry(.2, tick, NULL, NX_MODALRESPTHRESHOLD);
}
void nextstep_everyday_start(const char *directory)
{
	char path[4096];
	if (strlen(directory) > 4000) exit(64);
	sprintf(path, "%s/everyday-results.txt", directory);
	report = fopen(path, "w");
	if (!report) exit(65);
	fixture = [[NSString stringWithFormat:@"file://%s/location.html", directory] retain];
	controller = [nextstep_browser_windows objectAtIndex:0];
	[controller openUrlString:[NSString stringWithFormat:@"file://%s/controls.html", directory]];
	timer = DPSAddTimedEntry(.2, tick, NULL, NX_MODALRESPTHRESHOLD);
	if (!timer) exit(67);
}
