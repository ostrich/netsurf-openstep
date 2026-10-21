/* SPDX-License-Identifier: GPL-2.0-or-later */
#import "platform.h"
#import "text.h"
#import <foundation/NSData.h>
#include <stdio.h>
#include <string.h>
#include <libnsfb.h>
#include <libnsfb_plot.h>
#include "utils/nsurl.h"
#include "content/handlers/javascript/js.h"
#include "netsurf/plot_style.h"
#include "framebuffer/font.h"

/* Runs after normal browser initialization, before connecting to WindowServer.
 * GUI behavior and actual page rendering require separate acceptance tests. */
int nextstep_smoke_test(void)
{
	struct nsurl *url = NULL;
	nsfb_t *surface;
	unsigned char *bytes = NULL;
	int stride = 0, width = 0, failures = 0;
	nsfb_bbox_t clip = {0, 0, 8, 8};
	jsheap *heap = NULL;
	NSString *text;
	NSData *encoded;
	const unsigned char utf8[] = {0xc3, 0xa9};
	plot_font_style_t style = {
		.family = PLOT_FONT_FAMILY_SANS_SERIF, .size = 12 * PLOT_STYLE_SCALE,
		.weight = 400, .flags = 0
	};
#define CHECK(value, name) do { \
	if (!(value)) { fprintf(stderr, "NETSURF-SMOKE FAIL %s\n", name); failures++; } \
	else { printf("NETSURF-SMOKE PASS %s\n", name); } fflush(stdout); \
} while (0)
	CHECK(nsurl_create("https://example.org/test?q=next", &url) == NSERROR_OK,
		"URL parsing");
	CHECK(url != NULL && strcmp(nsurl_access(url), "https://example.org/test?q=next") == 0,
		"URL round trip");
	if (url != NULL) nsurl_unref(url);
	text = nextstep_new_utf8_string(utf8, 2);
	CHECK(text != nil && [text length] == 1 && [text characterAtIndex:0] == 0xe9,
		"UTF-8 decoding to Foundation");
	encoded = nextstep_utf8_data(text);
	CHECK([encoded length] == 2 && memcmp([encoded bytes], utf8, 2) == 0,
		"Foundation encoding to UTF-8");
	[text release];
	{
		static const unsigned char supplementary[] = {0xf0, 0x9f, 0x98, 0x80};
		static const unsigned char invalid[] = {0xc0, 0xaf};
		text = nextstep_new_utf8_string(supplementary, sizeof(supplementary));
		encoded = nextstep_utf8_data(text);
		CHECK(text != nil && [text length] == 2 && [encoded length] == 4 &&
			memcmp([encoded bytes], supplementary, 4) == 0, "UTF-16 surrogate round trip");
		[text release];
		CHECK(nextstep_new_utf8_string(invalid, sizeof(invalid)) == nil,
			"invalid UTF-8 rejection");
	}
	surface = nsfb_new(NSFB_SURFACE_RAM);
	CHECK(surface != NULL, "framebuffer RAM registration");
	if (surface != NULL) {
		if (nsfb_set_geometry(surface, 8, 8, NSFB_FMT_XRGB8888) == 0 && nsfb_init(surface) == 0) {
			CHECK(nsfb_plot_set_clip(surface, &clip), "framebuffer clip setup");
			CHECK(nsfb_plot_point(surface, 0, 0, 0xff0000ff), "opaque pixel plotting");
			CHECK(nsfb_get_buffer(surface, &bytes, &stride) == 0 && bytes != NULL && stride >= 32,
				"framebuffer storage");
			if (bytes != NULL && stride >= 32) {
				printf("NETSURF-PIXEL %02x %02x %02x %02x\n", bytes[0], bytes[1], bytes[2], bytes[3]);
				CHECK(bytes[0] == 0 && bytes[1] == 0 && bytes[2] == 255,
					"framebuffer byte order");
			}
		} else { CHECK(false, "framebuffer initialization"); }
		nsfb_free(surface);
	}
	CHECK(fb_font_width(&style, "NetSurf", 7, &width) == NSERROR_OK && width > 0,
		"FreeType font loading and measurement");
	CHECK(js_newheap(10, &heap) == NSERROR_OK && heap != NULL,
		"JavaScript heap initialization");
	if (heap != NULL) js_destroyheap(heap);
	printf("NETSURF-SMOKE %d\n", failures);
	return failures ? 1 : 0;
#undef CHECK
}
