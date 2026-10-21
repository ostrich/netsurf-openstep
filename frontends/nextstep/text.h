/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef NETSURF_NEXTSTEP_TEXT_H
#define NETSURF_NEXTSTEP_TEXT_H
#import "platform.h"
#import <foundation/NSData.h>
/* The string is retained; the data result is autoreleased. Invalid input
 * returns nil. NEXTSTEP Foundation's NSUTFStringEncoding is not relied upon. */
NSString *nextstep_new_utf8_string(const void *bytes, size_t length);
NSData *nextstep_utf8_data(NSString *string);
#endif
