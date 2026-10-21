/* SPDX-License-Identifier: GPL-2.0-or-later */
#import "text.h"
#include <limits.h>
#include <utf8proc.h>

NSString *nextstep_new_utf8_string(const void *input, size_t length)
{
	const utf8proc_uint8_t *bytes = input;
	unichar *units;
	size_t offset = 0;
	unsigned count = 0;
	NSString *result;
	if ((input == NULL && length != 0) || length > UINT_MAX / sizeof(*units)) return nil;
	units = malloc(length ? length * sizeof(*units) : sizeof(*units));
	if (units == NULL) return nil;
	while (offset < length) {
		utf8proc_int32_t scalar;
		utf8proc_ssize_t used = utf8proc_iterate(bytes + offset, length - offset, &scalar);
		if (used < 1) { free(units); return nil; }
		offset += used;
		if (scalar > 0xffff) {
			scalar -= 0x10000;
			units[count++] = 0xd800 | (scalar >> 10);
			units[count++] = 0xdc00 | (scalar & 0x3ff);
		} else {
			units[count++] = scalar;
		}
	}
	result = [[NSString alloc] initWithCharacters:units length:count];
	free(units);
	return result;
}

NSData *nextstep_utf8_data(NSString *string)
{
	unsigned length, i, count = 0;
	utf8proc_uint8_t *bytes;
	NSData *result;
	if (string == nil) return nil;
	length = [string length];
	if (length > UINT_MAX / 3) return nil;
	bytes = malloc(length ? length * 3 : 1);
	if (bytes == NULL) return nil;
	for (i = 0; i < length; i++) {
		utf8proc_int32_t scalar = [string characterAtIndex:i];
		utf8proc_ssize_t used;
		if (scalar >= 0xd800 && scalar <= 0xdbff) {
			unsigned low;
			if (++i == length) { free(bytes); return nil; }
			low = [string characterAtIndex:i];
			if (low < 0xdc00 || low > 0xdfff) { free(bytes); return nil; }
			scalar = 0x10000 + ((scalar - 0xd800) << 10) + low - 0xdc00;
		} else if (scalar >= 0xdc00 && scalar <= 0xdfff) {
			free(bytes); return nil;
		}
		used = utf8proc_encode_char(scalar, bytes + count);
		if (used < 1) { free(bytes); return nil; }
		count += used;
	}
	result = [NSData dataWithBytes:bytes length:count];
	free(bytes);
	return result;
}
