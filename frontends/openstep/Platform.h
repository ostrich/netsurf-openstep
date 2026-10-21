/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef NETSURF_OPENSTEP_PLATFORM_H
#define NETSURF_OPENSTEP_PLATFORM_H
#ifdef NETSURF_NEXTSTEP
#import "../nextstep/platform.h"
#else
#import <Foundation/Foundation.h>
#import <AppKit/AppKit.h>
#endif

#include <string.h>
#ifdef NETSURF_NEXTSTEP
#import "../nextstep/text.h"
#endif
static inline NSString *netsurf_string_from_utf8(const char *bytes)
{
	if (bytes == NULL) return nil;
#ifdef NETSURF_NEXTSTEP
	return [nextstep_new_utf8_string(bytes, strlen(bytes)) autorelease];
#else
	return [NSString stringWithCString:bytes];
#endif
}

#endif
