/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <stdlib.h>
#import "platform.h"
#include "utils/errors.h"
#include "schedule.h"
#include "netsurf/misc.h"

struct scheduled_callback {
	struct scheduled_callback *next;
	void (*function)(void *);
	void *context;
	DPSTimedEntry timer;
};

/* NetSurf and DPS invoke these operations on the application's main thread. */
static struct scheduled_callback *callbacks;

static void unlink_callback(struct scheduled_callback *item)
{
	struct scheduled_callback **link;
	for (link = &callbacks; *link != NULL; link = &(*link)->next) {
		if (*link == item) {
			*link = item->next;
			return;
		}
	}
}

static void perform_callback(DPSTimedEntry timer, double now, void *context)
{
	struct scheduled_callback *item = context;
	void (*function)(void *) = item->function;
	void *argument = item->context;
	NSAutoreleasePool *pool = [NSAutoreleasePool new];
	(void)now;
	DPSRemoveTimedEntry(timer);
	unlink_callback(item);
	/* A callback may immediately schedule or cancel itself. Retire its old
	 * node before invoking application code so no stale timer owns it. */
	free(item);
	function(argument);
	[pool release];
}

static nserror schedule_callback(int milliseconds, void (*function)(void *),
		void *context)
{
	struct scheduled_callback *item, *old;
	item = NULL;
	if (milliseconds >= 0) {
		item = calloc(1, sizeof(*item));
		if (item == NULL) {
			return NSERROR_NOMEM;
		}
		item->function = function;
		item->context = context;
		item->timer = DPSAddTimedEntry(milliseconds > 0 ?
			(double)milliseconds / 1000.0 : 0.001,
			perform_callback, item, NX_MODALRESPTHRESHOLD);
		if (item->timer == NULL) {
			free(item);
			return NSERROR_NOMEM;
		}
	}
	for (old = callbacks; old != NULL; old = old->next) {
		if (old->function == function && old->context == context) {
			DPSRemoveTimedEntry(old->timer);
			unlink_callback(old);
			free(old);
			break;
		}
	}
	if (item != NULL) {
		item->next = callbacks;
		callbacks = item;
	}
	return NSERROR_OK;
}

void nextstep_schedule_shutdown(void)
{
	while (callbacks != NULL) {
		struct scheduled_callback *item = callbacks;
		callbacks = item->next;
		DPSRemoveTimedEntry(item->timer);
		free(item);
	}
}

struct gui_misc_table nextstep_misc_table = {
	.schedule = schedule_callback
};
