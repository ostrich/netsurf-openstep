/* SPDX-License-Identifier: GPL-2.0-or-later */
#import "platform.h"
struct browser_window;
@interface NextstepPlotView : View {
	struct browser_window *browser;
	BOOL showCaret;
	BOOL dragging;
	NXPoint dragStart;
	NXRect caretRect;
}
- setBrowser:(struct browser_window *)value;
- placeCaretAtX:(int)x y:(int)y height:(int)height;
- removeCaret;
@end
