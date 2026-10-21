/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Root-only disposable-guest probe: inherit the desktop task's bootstrap
 * namespace, drop to its account, then exec a GUI client. Never setuid. */
#include <mach/mach.h>
#include <mach/mach_interface.h>
#include <mach/task_special_ports.h>
#include <pwd.h>
#include <grp.h>
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv)
{
	task_t desktop;
	port_t bootstrap, previous;
	kern_return_t status;
	struct passwd *account, root_account;
	const char *name;
	int root_mode;
	char user[128], home[4096], logname[128];
	char *environment[7], *end;
	long pid;
	uid_t uid;
	gid_t gid;
	if (argc < 4 || geteuid() != 0) return 64;
	errno = 0;
	pid = strtol(argv[1], &end, 10);
	if (errno || *end || pid <= 0 || pid > INT_MAX) return 64;
	root_mode = strcmp(argv[2], "@root") == 0;
	if (root_mode) {
		/* Owned rc-launched tests already run as root. Avoid a NetInfo user
		 * lookup merely to rediscover that identity while daemons start. */
		if (getuid() != 0) return 64;
		memset(&root_account, 0, sizeof(root_account));
		root_account.pw_dir = "/";
		account = &root_account;
		name = "root";
	} else {
		account = getpwnam(argv[2]);
		name = argv[2];
	}
	if (account == NULL || strlen(argv[2]) > 100 || strlen(account->pw_dir) > 4000) return 65;
	status = task_by_unix_pid(task_self(), (int)pid, &desktop);
	if (status != KERN_SUCCESS) { fprintf(stderr, "desktop task: %d\n", status); return 66; }
	status = task_get_bootstrap_port(desktop, &bootstrap);
	if (status != KERN_SUCCESS) { fprintf(stderr, "desktop bootstrap: %d\n", status); return 67; }
	status = task_get_bootstrap_port(task_self(), &previous);
	if (status != KERN_SUCCESS) return 68;
	fprintf(stderr, "desktop bootstrap differs: %d\n", bootstrap != previous);
	status = task_set_bootstrap_port(task_self(), bootstrap);
	if (status != KERN_SUCCESS) { fprintf(stderr, "set bootstrap: %d\n", status); return 69; }
	sprintf(user, "USER=%s", name);
	sprintf(logname, "LOGNAME=%s", name);
	sprintf(home, "HOME=%s", account->pw_dir);
	uid = account->pw_uid;
	gid = account->pw_gid;
	port_deallocate(task_self(), previous);
	port_deallocate(task_self(), bootstrap);
	port_deallocate(task_self(), desktop);
	if ((!root_mode && initgroups(name, gid) != 0) || setgid(gid) != 0 || setuid(uid) != 0) { perror("desktop account"); return 70; }
	environment[0] = user;
	environment[1] = logname;
	environment[2] = home;
	environment[3] = "PATH=/usr/local/bin:/usr/bin:/bin";
	environment[4] = "SHELL=/bin/sh";
	environment[5] = "NETSURF_STARTUP_TRACE=1";
	environment[6] = NULL;
	execve(argv[3], argv + 3, environment);
	perror("desktop exec");
	return 71;
}
