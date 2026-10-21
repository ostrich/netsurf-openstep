/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef NETSURF_NEXTSTEP_PLATFORM_H
#define NETSURF_NEXTSTEP_PLATFORM_H

#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>

#import <foundation/NSObject.h>
#import <foundation/NSString.h>
#import <foundation/NSArray.h>
#import <foundation/NSDictionary.h>
#import <foundation/NSBundle.h>
#import <foundation/NSAutoreleasePool.h>
#import <foundation/NSPathUtilities.h>
#import <foundation/NSUtilities.h>
#import <appkit/Application.h>
#import <appkit/Window.h>
#import <appkit/View.h>
#import <appkit/Button.h>
#import <appkit/TextField.h>
#import <appkit/ScrollView.h>
#import <appkit/Menu.h>
#import <appkit/NXImage.h>
#import <appkit/Pasteboard.h>
#import <appkit/graphics.h>
#import <dpsclient/dpsclient.h>

/* Shared browser callbacks exchange geometry by value. These are data-layout
 * aliases, not replacements for OPENSTEP AppKit classes or message semantics.
 */
typedef NXPoint NSPoint;
typedef NXSize NSSize;
typedef NXRect NSRect;

static inline NSPoint NSMakePoint(float x, float y)
{
	NSPoint point = {x, y};
	return point;
}

static inline NSSize NSMakeSize(float width, float height)
{
	NSSize size = {width, height};
	return size;
}

static inline NSRect NSMakeRect(float x, float y, float width, float height)
{
	NSRect rect = {{x, y}, {width, height}};
	return rect;
}

#define NSMinX(rect) ((rect).origin.x)
#define NSMinY(rect) ((rect).origin.y)
#define NSMaxX(rect) ((rect).origin.x + (rect).size.width)
#define NSMaxY(rect) ((rect).origin.y + (rect).size.height)

void nextstep_display_windows(void);

#endif
