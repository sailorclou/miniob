/*
 * XXX This sample code was once meant to show how to use the basic Libevent
 * interfaces, but it never worked on non-Unix platforms, and some of the
 * interfaces have changed since it was first written.  It should probably
 * be removed or replaced with something better.
 *
 * Compile with:
 * cc -I/usr/local/include -o time-test time-test.c -L/usr/local/lib -levent
 */

#include <sys/types.h>

#include <event2/event-config.h>

#include <sys/stat.h>
#ifndef _WIN32
#include <sys/queue.h>
#include <unistd.h>
#endif
#include <time.h>
#ifdef EVENT__HAVE_SYS_TIME_H
#include <sys/time.h>
#endif
#include <fcntl.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <signal.h>
#include <event2/event.h>
#include <event2/event_struct.h>
#include <event2/util.h>

#ifdef _WIN32
#include <winsock2.h>
#endif

struct timeval lasttime;

int event_is_persistent;

static void
timeout_cb(evutil_socket_t fd, short event, void *arg)
{
	struct timeval newtime, difference;
	struct event *timeout = arg;
	double elapsed;

	evutil_gettimeofday(&newtime, NULL);
	evutil_timersub(&newtime, &lasttime, &difference);
	elapsed = difference.tv_sec +
	    (difference.tv_usec / 1.0e6);

	printf("timeout_cb called at %d: %.3f seconds elapsed.\n",
	    (int)newtime.tv_sec, elapsed);
	lasttime = newtime;

	if (! event_is_persistent) {
		struct timeval tv;
		evutil_timerclear(&tv);
		tv.tv_sec = 2;
		event_add(timeout, &tv);
	}
}

static void
signal_cb(evutil_socket_t sig, short events, void *user_data)
{
	struct event_base *base = user_data;

	printf("Caught an interrupt signal; exiting cleanly.\n");

	event_base_loopexit(base, NULL);
}

int
main(int argc, char **argv)
{
	struct event *timeout,*signal_event;
	struct timeval tv;
	struct event_base *base;
	int flags;

#ifdef _WIN32
	WORD wVersionRequested;
	WSADATA wsaData;

	wVersionRequested = MAKEWORD(2, 2);

	(void)WSAStartup(wVersionRequested, &wsaData);
#endif

	if (argc == 2 && !strcmp(argv[1], "-p")) {
		event_is_persistent = 1;
		flags = EV_PERSIST;
	} else {
		event_is_persistent = 0;
		flags = 0;
	}

	/* Initialize the event library */
	base = event_base_new();

	/* Initialize one event */
	timeout = event_new(base, -1, flags, timeout_cb, event_self_cbarg());
	signal_event = evsignal_new(base, SIGINT, signal_cb, (void*)base );
	if (timeout == NULL) {
		fprintf(stderr, "Couldn't create event");
		goto err;
	}
	if (signal_event == NULL) {
		fprintf(stderr, "Couldn't create event");
		goto err;
	}
	evutil_timerclear(&tv);
	tv.tv_sec = 2;
	event_add(timeout, &tv);
	event_add(signal_event, NULL);

	evutil_gettimeofday(&lasttime, NULL);

	setbuf(stdout, NULL);
	setbuf(stderr, NULL);

	event_base_dispatch(base);

	event_free(signal_event);
	event_free(timeout);
	event_base_free(base);

	return (0);
err:
	if (signal_event)
		event_free(signal_event);
	if (timeout)
		event_free(timeout);
	if (base)
		event_base_free(base);
	return (1);
}

