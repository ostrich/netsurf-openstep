/* SPDX-License-Identifier: GPL-2.0-or-later */
#import "platform.h"
#import "text.h"
#import <foundation/NSData.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include "netsurf/clipboard.h"

/* Native pasteboard text is NEXTSTEP encoding. NetSurf exchanges UTF-8.
 * NSString performs that conversion; copying C strings would corrupt accents.
 */
static void clipboard_get(char **buffer, size_t *length)
{
	Pasteboard *board = [Pasteboard new];
	char *bytes = NULL;
	int count = 0;
	int allocated_count = 0;
	NSString *text = nil;
	NSData *utf8;
	*buffer = NULL;
	*length = 0;
	if ([board readType:NXAsciiPboardType data:&bytes length:&count] &&
			bytes != NULL && count >= 0) {
		allocated_count = count;
		if (count > 0 && bytes[count - 1] == '\0') count--;
		text = [[NSString alloc] initWithCString:bytes length:count];
	}
	if (bytes != NULL) [board deallocatePasteboardData:bytes length:allocated_count];
	if (text == nil) return;
	utf8 = nextstep_utf8_data(text);
	if (utf8 != nil) {
		*buffer = malloc([utf8 length] + 1);
		if (*buffer != NULL) {
			*length = [utf8 length];
			memcpy(*buffer, [utf8 bytes], *length);
			(*buffer)[*length] = '\0';
		}
	}
	[text release];
}

static void clipboard_set(const char *buffer, size_t length,
		nsclipboard_styles styles[], int n_styles)
{
	const char *types[] = {NXAsciiPboardType};
	NSString *text;
	NSData *native;
	Pasteboard *board;
	(void)styles;
	(void)n_styles;
	if (length > INT_MAX) return;
	text = nextstep_new_utf8_string(buffer, length);
	if (text == nil) return;
	native = [text dataUsingEncoding:[NSString defaultCStringEncoding]
		allowLossyConversion:YES];
	if (native != nil && [native length] <= INT_MAX) {
		board = [Pasteboard new];
		[board declareTypes:types num:1 owner:nil];
		[board writeType:NXAsciiPboardType data:[native bytes] length:[native length]];
	}
	[text release];
}

struct gui_clipboard_table nextstep_clipboard_table = {
	.get = clipboard_get,
	.set = clipboard_set
};
