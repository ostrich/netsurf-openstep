/* SPDX-License-Identifier: GPL-2.0-or-later */
/* C89/native AppKit control, deliberately independent of NetSurf/Foundation. */
#import <appkit/Application.h>
#import <appkit/Window.h>
#import <appkit/View.h>
#import <appkit/TextField.h>
#import <appkit/graphics.h>
#import <dpsclient/dpsclient.h>
#import <dpsclient/psops.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static Window *window;
static unsigned draws, stage;
static const char *label;

@interface ProbeView : View
@end
@implementation ProbeView
- drawSelf:(const NXRect *)rects :(int)count
{
    NXRect r;
    (void)rects; (void)count;
    [self getBounds:&r];
    fprintf(stderr, "PROBE %s draw %u bounds %g %g\n", label, ++draws,
            r.size.width, r.size.height);
    fflush(stderr);
    PSsetgray(1); NXRectFill(&r);
    r.origin.x = 20; r.origin.y = 20;
    r.size.width = 180; r.size.height = 80;
    PSsetrgbcolor(0, .7, .2); NXRectFill(&r);
    return self;
}
@end

static void tick(DPSTimedEntry timer, double now, void *context)
{
    NXRect r;
    (void)context;
    DPSRemoveTimedEntry(timer);
    fprintf(stderr, "PROBE %s stage %u draws %u\n",label,stage,draws);
    fflush(stderr);
    if (stage == 0) {
        fprintf(stderr, "PROBE %s display begin\n", label); fflush(stderr);
        [window display]; [window flushWindow];
        fprintf(stderr, "PROBE %s display returned\n", label); fflush(stderr);
    } else if (stage == 1) {
        fprintf(stderr, "PROBE %s resize begin\n", label); fflush(stderr);
        [window sizeWindow:440 :300];
        fprintf(stderr, "PROBE %s resize returned\n", label); fflush(stderr);
        [window display]; [window flushWindow];
    } else {
        [window getFrame:&r];
        fprintf(stderr, "PROBE %s complete draws=%u frame=%gx%g\n",label,draws,r.size.width,r.size.height);
        fflush(stderr);
        [NXApp terminate:nil];
        return;
    }
    stage++; (void)now;
    DPSAddTimedEntry(5, tick, NULL, NX_MODALRESPTHRESHOLD);
}

int main(int argc, char **argv)
{
    NXRect r = {{100,100},{500,340}};
    NXRect vr = {{0,0},{500,300}};
    NXRect tr = {{20,310},{460,22}};
    id view, text;
    label = argc > 1 ? argv[1] : "unknown";
    fprintf(stderr,"PROBE %s application begin\n",label); fflush(stderr);
    [Application new];
    window = [[Window alloc] initContent:&r style:NX_RESIZEBARSTYLE
        backing:NX_BUFFERED buttonMask:NX_CLOSEBUTTONMASK defer:NO];
    [window setTitle:label];
    view = [[ProbeView alloc] initFrame:&vr];
    [view setAutosizing:NX_WIDTHSIZABLE | NX_HEIGHTSIZABLE];
    [[window contentView] addSubview:view];
    text = [[TextField alloc] initFrame:&tr];
    [text setStringValue:"AppKit drawing and resize control"];
    [[window contentView] addSubview:text];
    [[window contentView] setAutoresizeSubviews:YES];
    [window display]; [window makeKeyAndOrderFront:nil]; [window flushWindow];
    fprintf(stderr,"PROBE %s event loop\n",label); fflush(stderr);
    DPSAddTimedEntry(5,tick,NULL,NX_MODALRESPTHRESHOLD);
    [NXApp run];
    return draws ? 0 : 1;
}
