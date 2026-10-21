/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <libwapcaplet/libwapcaplet.h>

static void count_string(lwc_string *string, void *context)
{
	unsigned *count = context;
	(void)string;
	(*count)++;
}

int main(void)
{
	unsigned iteration, count;
	lwc_string *first, *same, *lower;
	bool equal;
	lwc_string_unref(NULL);
	for (iteration = 0; iteration < 1000; iteration++) {
		assert(lwc_intern_string("NetSurf", 7, &first) == lwc_error_ok);
		assert(lwc_intern_string("NetSurf", 7, &same) == lwc_error_ok);
		assert(first == same);
		assert(lwc_string_tolower(first, &lower) == lwc_error_ok);
		assert(lwc_string_caseless_isequal(first, lower, &equal) == lwc_error_ok && equal);
		lwc_string_unref(first);
		lwc_string_unref(NULL);
		lwc_string_unref(same);
		lwc_string_unref(lower);
	}
	count = 0;
	lwc_iterate_strings(count_string, &count);
	assert(count == 0);
	return 0;
}
