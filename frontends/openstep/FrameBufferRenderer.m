/*
 * Copyright 2026 Bastian Mueller <bastian@turbolent.com>
 *
 * This file is part of NetSurf, http://www.netsurf-browser.org/
 *
 * NetSurf is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; version 2 of the License.
 *
 * NetSurf is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#import "FrameBufferRenderer.h"

#include <stdlib.h>
#include <limits.h>
#include <math.h>

#import <libnsfb.h>
#import <libnsfb_plot.h>
#ifndef NETSURF_NEXTSTEP
#import <AppKit/NSGraphics.h>
#endif

#import "netsurf/browser_window.h"
#import "netsurf/plotters.h"
#import "framebuffer/framebuffer.h"

/* The framebuffer is opaque, so the native NX bitmap upload needs only RGB.
 * Retain the established four-component OPENSTEP upload separately. */
#ifdef NETSURF_NEXTSTEP
#define OPENSTEP_UPLOAD_COMPONENTS 3
#else
#define OPENSTEP_UPLOAD_COMPONENTS 4
#endif

static nsfb_t *openstep_fb_surface;
static unsigned char *openstep_fb_upload;
static int openstep_fb_upload_size;
static int openstep_fb_width;
static int openstep_fb_height;

#ifdef NETSURF_NEXTSTEP_QUALIFY
NSSize nextstep_framebuffer_test_size(void)
{
	return NSMakeSize(openstep_fb_width, openstep_fb_height);
}
#endif

static BOOL openstep_framebuffer_ensure_surface(NSRect rect)
{
	double right = NSMaxX(rect), bottom = NSMaxY(rect);
	int width, height;

	/* libnsfb uses signed integer byte counts. Reject non-finite or excessive
	 * document extents before converting coordinates or multiplying sizes. */
	if (!(right >= 0 && bottom >= 0 &&
			right <= INT_MAX / 4 && bottom <= INT_MAX / 4)) return NO;
	width = (int)right;
	height = (int)bottom;

	if (width < 1) {
		width = 1;
	}
	if (height < 1) {
		height = 1;
	}

	if (width > INT_MAX / 4 / height) return NO;

	if (openstep_fb_surface != NULL &&
			width == openstep_fb_width &&
			height == openstep_fb_height) {
		return YES;
	}

	if (openstep_fb_surface != NULL) {
		nsfb_free(openstep_fb_surface);
		openstep_fb_surface = NULL;
	}
	if (openstep_fb_upload != NULL) {
		free(openstep_fb_upload);
		openstep_fb_upload = NULL;
		openstep_fb_upload_size = 0;
	}

	openstep_fb_surface = nsfb_new(NSFB_SURFACE_RAM);
	if (openstep_fb_surface == NULL) {
		return NO;
	}

	if (nsfb_set_geometry(openstep_fb_surface,
			width,
			height,
			NSFB_FMT_XRGB8888) == -1) {
		nsfb_free(openstep_fb_surface);
		openstep_fb_surface = NULL;
		return NO;
	}

	if (nsfb_init(openstep_fb_surface) == -1) {
		nsfb_free(openstep_fb_surface);
		openstep_fb_surface = NULL;
		return NO;
	}

	openstep_fb_width = width;
	openstep_fb_height = height;
	return YES;
}

static BOOL openstep_framebuffer_ensure_upload_buffer(void)
{
	int size = openstep_fb_width * openstep_fb_height * OPENSTEP_UPLOAD_COMPONENTS;
	unsigned char *upload;

	if (openstep_fb_upload != NULL && size == openstep_fb_upload_size) {
		return YES;
	}

	upload = realloc(openstep_fb_upload, size);
	if (upload == NULL) {
		free(openstep_fb_upload);
		openstep_fb_upload = NULL;
		openstep_fb_upload_size = 0;
		return NO;
	}

	openstep_fb_upload = upload;
	openstep_fb_upload_size = size;
	return YES;
}

static void openstep_framebuffer_repack_xrgb(unsigned char *src,
		int srcStride)
{
	int x;
	int y;
	unsigned char *dst;

	for (y = 0; y < openstep_fb_height; y++) {
		unsigned char *srcRow = src + y * srcStride;
		unsigned char *dstRow = openstep_fb_upload +
				y * openstep_fb_width * OPENSTEP_UPLOAD_COMPONENTS;

		for (x = 0; x < openstep_fb_width; x++) {
			dst = dstRow + x * OPENSTEP_UPLOAD_COMPONENTS;
			dst[0] = srcRow[x * 4 + 2];
			dst[1] = srcRow[x * 4 + 1];
			dst[2] = srcRow[x * 4 + 0];
#ifndef NETSURF_NEXTSTEP
			dst[3] = 0xff;
#endif
		}
	}
}

static unsigned char openstep_framebuffer_gamma_compensate(unsigned char v)
{
	unsigned int c = v;

	return (unsigned char)(((c * c + 127) / 255 + c) / 2);
}

static void openstep_framebuffer_apply_gamma_compensation(void)
{
	int x;
	int y;

	for (y = 0; y < openstep_fb_height; y++) {
		unsigned char *row = openstep_fb_upload +
				y * openstep_fb_width * OPENSTEP_UPLOAD_COMPONENTS;

		for (x = 0; x < openstep_fb_width; x++) {
			unsigned char *dst = row + x * OPENSTEP_UPLOAD_COMPONENTS;

			dst[0] = openstep_framebuffer_gamma_compensate(dst[0]);
			dst[1] = openstep_framebuffer_gamma_compensate(dst[1]);
			dst[2] = openstep_framebuffer_gamma_compensate(dst[2]);
		}
	}
}

BOOL openstep_framebuffer_render_browser(struct browser_window *browser,
		NSRect rect,
		BOOL showCaret,
		NSRect caretRect)
{
	struct redraw_context ctx;
	struct rect clip;
	struct plot_style_s clear_style;
	nsfb_t *previous;
	unsigned char *buffer;
	int stride;
	const unsigned char *planes[5];
#ifdef NETSURF_NEXTSTEP
	int origin_x, origin_y;
	NSRect surface_rect;
	/* Render in viewport coordinates. Allocating up to the document offset
	 * wastes memory, repacks hidden rows and makes deep scrolling expensive.
	 * Round outwards so fractional ClipView bounds cannot leave an edge dirty. */
	if (!(rect.origin.x >= 0 && rect.origin.y >= 0 &&
		(double)NSMaxX(rect) <= INT_MAX && (double)NSMaxY(rect) <= INT_MAX &&
		rect.size.width > 0 && rect.size.height > 0)) return NO;
	origin_x = (int)floor(rect.origin.x);
	origin_y = (int)floor(rect.origin.y);
	surface_rect = NSMakeRect(0, 0,
		ceil((double)NSMaxX(rect)) - origin_x,
		ceil((double)NSMaxY(rect)) - origin_y);
#endif

	if (browser == NULL || !openstep_framebuffer_ensure_surface(
#ifdef NETSURF_NEXTSTEP
			surface_rect
#else
			rect
#endif
			)) {
		return NO;
	}

	ctx.interactive = true;
	ctx.background_images = true;
	ctx.plot = &fb_plotters;

#ifdef NETSURF_NEXTSTEP
	clip.x0 = clip.y0 = 0;
	clip.x1 = openstep_fb_width;
	clip.y1 = openstep_fb_height;
#else
	clip.x0 = NSMinX(rect);
	clip.y0 = NSMinY(rect);
	clip.x1 = NSMaxX(rect);
	clip.y1 = NSMaxY(rect);
#endif

	previous = framebuffer_set_surface(openstep_fb_surface);
	fb_plotters.clip(&ctx, &clip);
	clear_style.stroke_type = PLOT_OP_TYPE_NONE;
	clear_style.fill_type = PLOT_OP_TYPE_SOLID;
	clear_style.fill_colour = 0x00ffffff;
	fb_plotters.rectangle(&ctx, &clear_style, &clip);
	browser_window_redraw(browser,
#ifdef NETSURF_NEXTSTEP
		-origin_x, -origin_y,
#else
		0, 0,
#endif
		&clip, &ctx);

	if (showCaret) {
		nsfb_bbox_t caret;
		caret.x0 = caretRect.origin.x;
		caret.y0 = caretRect.origin.y;
#ifdef NETSURF_NEXTSTEP
		caret.x0 -= origin_x;
		caret.y0 -= origin_y;
#endif
		caret.x1 = caret.x0 + caretRect.size.width;
		caret.y1 = caret.y0 + caretRect.size.height;
		nsfb_plot_rectangle_fill(openstep_fb_surface,
				&caret,
				0x00000000);
	}

	framebuffer_set_surface(previous);

	buffer = NULL;
	stride = 0;
	if (nsfb_get_buffer(openstep_fb_surface, &buffer, &stride) == -1 ||
			buffer == NULL || stride <= 0) {
		return NO;
	}
	if (!openstep_framebuffer_ensure_upload_buffer()) {
		return NO;
	}
	openstep_framebuffer_repack_xrgb(buffer, stride);
	openstep_framebuffer_apply_gamma_compensation();

	planes[0] = openstep_fb_upload;
	planes[1] = NULL;
	planes[2] = NULL;
	planes[3] = NULL;
	planes[4] = NULL;
#ifdef NETSURF_NEXTSTEP
	NXRect destination = NSMakeRect(origin_x, origin_y,
		openstep_fb_width, openstep_fb_height);
	NXDrawBitmap(&destination,
#else
	NSDrawBitmap(NSMakeRect(0, 0, openstep_fb_width, openstep_fb_height),
#endif
			openstep_fb_width,
			openstep_fb_height,
			8,
			OPENSTEP_UPLOAD_COMPONENTS,
			8 * OPENSTEP_UPLOAD_COMPONENTS,
			openstep_fb_width * OPENSTEP_UPLOAD_COMPONENTS,
			NO,
#ifdef NETSURF_NEXTSTEP
			NO,
#else
			YES,
#endif
#ifdef NETSURF_NEXTSTEP
			NX_RGBColorSpace,
#else
			NSDeviceRGBColorSpace,
#endif
			planes);
	return YES;
}
