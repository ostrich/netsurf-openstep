/* SPDX-License-Identifier: GPL-2.0-or-later */
#import "PlotView.h"
#import "../openstep/FrameBufferRenderer.h"
#import <appkit/ClipView.h>
#import <dpsclient/psops.h>
#import <foundation/NSData.h>
#include "netsurf/browser_window.h"
#include "netsurf/keypress.h"
#include "netsurf/mouse.h"
#include <stdio.h>
#include <stdlib.h>

static browser_mouse_state modifiers(NXEvent *event)
{
	browser_mouse_state state = 0;
	if (event->flags & NX_SHIFTMASK) state |= BROWSER_MOUSE_MOD_1;
	if (event->flags & NX_CONTROLMASK) state |= BROWSER_MOUSE_MOD_2;
	if (event->flags & NX_ALTERNATEMASK) state |= BROWSER_MOUSE_MOD_3;
	return state;
}

@implementation NextstepPlotView
- initFrame:(const NXRect *)rect
{
	[super initFrame:rect];
	[self setFlipped:YES];
	[self setOpaque:YES];
	return self;
}
- setNeedsDisplay:(BOOL)flag
{
	needs_redraw = flag;
	return [super setNeedsDisplay:flag];
}
- displayPendingContent
{
	if (needs_redraw && [self canDraw]) {
		needs_redraw = NO;
		[self display];
	}
	return self;
}
- setBrowser:(struct browser_window *)value
{
	browser = value;
	[self setNeedsDisplay:YES];
	return self;
}
- placeCaretAtX:(int)x y:(int)y height:(int)height
{
	caretRect = NSMakeRect(x, y, 1, height);
	showCaret = YES;
	[self setNeedsDisplay:YES];
	return self;
}
- removeCaret
{
	showCaret = NO;
	[self setNeedsDisplay:YES];
	return self;
}
- drawSelf:(const NXRect *)rects :(int)count
{
	NXRect visible;
	(void)rects;
	(void)count;
	[self getVisibleRect:&visible];
	if (getenv("NETSURF_STARTUP_TRACE")) {
		static unsigned count;
		if (count++ < 8) fprintf(stderr, "NetSurf: draw browser=%p visible=%g,%g %gx%g\n",
			(void *)browser, visible.origin.x, visible.origin.y,
			visible.size.width, visible.size.height);
	}
	PSsetgray(1);
	NXRectFill(&visible);
	if (browser != NULL)
		openstep_framebuffer_render_browser(browser, visible, showCaret, caretRect);
	return self;
}
- (BOOL)acceptsFirstResponder { return YES; }
- (BOOL)acceptsFirstMouse { return YES; }
- mouseDown:(NXEvent *)event
{
	if (browser == NULL) return self;
	[[self window] makeFirstResponder:self];
	dragging = NO;
	dragStart = event->location;
	[self convertPoint:&dragStart fromView:nil];
	browser_window_mouse_click(browser, BROWSER_MOUSE_PRESS_1 | modifiers(event),
		dragStart.x, dragStart.y);
	return self;
}
- mouseDragged:(NXEvent *)event
{
	NXPoint point = event->location;
	float dx, dy;
	if (browser == NULL) return self;
	[self convertPoint:&point fromView:nil];
	dx = point.x - dragStart.x;
	dy = point.y - dragStart.y;
	if (!dragging && dx * dx + dy * dy >= 25) {
		dragging = YES;
		browser_window_mouse_click(browser, BROWSER_MOUSE_DRAG_1 | modifiers(event),
			dragStart.x, dragStart.y);
	}
	if (dragging) {
		browser_window_mouse_track(browser, BROWSER_MOUSE_HOLDING_1 |
			BROWSER_MOUSE_DRAG_ON | modifiers(event), point.x, point.y);
		[self autoscroll:event];
	}
	return self;
}
- mouseUp:(NXEvent *)event
{
	NXPoint point = event->location;
	browser_mouse_state state;
	if (browser == NULL) return self;
	[self convertPoint:&point fromView:nil];
	if (dragging) {
		dragging = NO;
		browser_window_mouse_track(browser, 0, point.x, point.y);
	} else {
		state = BROWSER_MOUSE_CLICK_1 | modifiers(event);
		if (event->data.mouse.click == 2) state |= BROWSER_MOUSE_DOUBLE_CLICK;
		browser_window_mouse_click(browser, state, point.x, point.y);
	}
	return self;
}
- mouseMoved:(NXEvent *)event
{
	NXPoint point = event->location;
	if (browser == NULL) return self;
	[self convertPoint:&point fromView:nil];
	browser_window_mouse_track(browser, modifiers(event), point.x, point.y);
	return self;
}
- keyDown:(NXEvent *)event
{
	uint32_t key = event->data.key.charCode;
	NXRect visible;
	if (browser == NULL) return self;
	/* Native symbol-set arrow keys are not Unicode key values. */
	if (event->data.key.charSet == NX_SYMBOLSET) {
		switch (key) {
		case 0xac: key = NS_KEY_LEFT; break;
		case 0xad: key = NS_KEY_UP; break;
		case 0xae: key = NS_KEY_RIGHT; break;
		case 0xaf: key = NS_KEY_DOWN; break;
		default: return [super keyDown:event];
		}
	} else {
		switch (key) {
		case '\r': key = NS_KEY_NL; break;
		case '\t': key = (event->flags & NX_SHIFTMASK) ? NS_KEY_SHIFT_TAB : NS_KEY_TAB; break;
		case 0x7f: case '\b': key = NS_KEY_DELETE_LEFT; break;
		case 0x1b: key = NS_KEY_ESCAPE; break;
		default:
			/* Translate a native character to the scalar value expected by NetSurf. */
			if (key >= 0x80 && key <= 0xff) {
				char byte = key;
				NSString *text = [[NSString alloc] initWithCString:&byte length:1];
				if (text == nil || [text length] == 0) { [text release]; return self; }
				key = [text characterAtIndex:0];
				[text release];
			}
		}
	}
	if (!browser_window_key_press(browser, key)) {
		[self getVisibleRect:&visible];
		if (key == NS_KEY_UP) visible.origin.y -= 20;
		else if (key == NS_KEY_DOWN) visible.origin.y += 20;
		else if (key == NS_KEY_LEFT) visible.origin.x -= 20;
		else if (key == NS_KEY_RIGHT) visible.origin.x += 20;
		else return [super keyDown:event];
		[self scrollPoint:&visible.origin];
	}
	return self;
}
- copy:sender { (void)sender; if (browser) browser_window_key_press(browser, NS_KEY_COPY_SELECTION); return self; }
- cut:sender { (void)sender; if (browser) browser_window_key_press(browser, NS_KEY_CUT_SELECTION); return self; }
- paste:sender { (void)sender; if (browser) browser_window_key_press(browser, NS_KEY_PASTE); return self; }
- selectAll:sender { (void)sender; if (browser) browser_window_key_press(browser, NS_KEY_SELECT_ALL); return self; }
@end
