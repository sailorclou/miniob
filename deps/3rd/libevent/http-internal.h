/*
 * Copyright 2001-2007 Niels Provos <provos@citi.umich.edu>
 * Copyright 2007-2012 Niels Provos and Nick Mathewson
 *
 * This header file contains definitions for dealing with HTTP requests
 * that are internal to libevent.  As user of the library, you should not
 * need to know about these.
 */

#ifndef HTTP_INTERNAL_H_INCLUDED_
#define HTTP_INTERNAL_H_INCLUDED_

#include "event2/event_struct.h"
#include "util-internal.h"
#include "defer-internal.h"

#define HTTP_CONNECT_TIMEOUT	45
#define HTTP_WRITE_TIMEOUT	50
#define HTTP_READ_TIMEOUT	50
#define HTTP_INITIAL_RETRY_TIMEOUT	2

enum message_read_status {
	ALL_DATA_READ = 1,
	MORE_DATA_EXPECTED = 0,
	DATA_CORRUPTED = -1,
	REQUEST_CANCELED = -2,
	DATA_TOO_LONG = -3
};

struct evbuffer;
struct addrinfo;
struct evhttp_request;

enum evhttp_connection_state {
	EVCON_DISCONNECTED,	/**< not currently connected not trying either*/
	EVCON_CONNECTING,	/**< tries to currently connect */
	EVCON_IDLE,		/**< connection is established */
	EVCON_READING_FIRSTLINE,/**< reading Request-Line (incoming conn) or
				 **< Status-Line (outgoing conn) */
	EVCON_READING_HEADERS,	/**< reading request/response headers */
	EVCON_READING_BODY,	/**< reading request/response body */
	EVCON_READING_TRAILER,	/**< reading request/response chunked trailer */
	EVCON_WRITING		/**< writing request/response headers/body */
};

struct event_base;

/* A client or server connection. */
struct evhttp_connection {
	/* we use this tailq only if this connection was created for an http
	 * server */
	TAILQ_ENTRY(evhttp_connection) next;

	struct bufferevent *bufev;

	struct event retry_ev;		/* for retrying connects */

	char *bind_address;		/* address to use for binding the src */
	ev_uint16_t bind_port;		/* local port for binding the src */

	char *address;			/* address to connect to */
	ev_uint16_t port;

#ifndef _WIN32
	char *unixsocket;
#endif
	size_t max_headers_size;
	ev_uint64_t max_body_size;

	int flags;
#define EVHTTP_CON_INCOMING	0x0001       /* only one request on it ever */
#define EVHTTP_CON_OUTGOING	0x0002       /* multiple requests possible */
#define EVHTTP_CON_CLOSEDETECT	0x0004   /* detecting if persistent close */
/* set when we want to auto free the connection */
#define EVHTTP_CON_AUTOFREE	EVHTTP_CON_PUBLIC_FLAGS_END
/* Installed when attempt to read HTTP error after write failed, see
 * EVHTTP_CON_READ_ON_WRITE_ERROR */
#define EVHTTP_CON_READING_ERROR	(EVHTTP_CON_AUTOFREE << 1)
/* Timeout is not default */
#define EVHTTP_CON_TIMEOUT_ADJUSTED	(EVHTTP_CON_READING_ERROR << 1)

	struct timeval timeout_connect;		/* timeout for connect phase */
	struct timeval timeout_read;		/* timeout for read */
	struct timeval timeout_write;		/* timeout for write */

	int retry_cnt;			/* retry count */
	int retry_max;			/* maximum number of retries */
	struct timeval initial_retry_timeout; /* Timeout for low long to wait
					       * after first failing attempt
					       * before retry */

	enum evhttp_connection_state state;

	/* for server connections, the http server they are connected with */
	struct evhttp *http_server;

	TAILQ_HEAD(evcon_requestq, evhttp_request) requests;

	void (*cb)(struct evhttp_connection *, void *);
	void *cb_arg;

	void (*closecb)(struct evhttp_connection *, void *);
	void *closecb_arg;

	struct event_callback read_more_deferred_cb;

	struct event_base *base;
	struct evdns_base *dns_base;
	int ai_family;

	evhttp_ext_method_cb ext_method_cmp;
};

/* A callback for an http server */
struct evhttp_cb {
	TAILQ_ENTRY(evhttp_cb) next;

	char *what;

	void (*cb)(struct evhttp_request *req, void *);
	void *cbarg;
};

/* both the http server as well as the rpc system need to queue connections */
TAILQ_HEAD(evconq, evhttp_connection);

/* WebSockets connections */
TAILQ_HEAD(evwsq, evws_connection);

/* each bound socket is stored in one of these */
struct evhttp_bound_socket {
	TAILQ_ENTRY(evhttp_bound_socket) next;

	struct evhttp *http;
	struct bufferevent* (*bevcb)(struct event_base *, void *);
	void *bevcbarg;

	struct evconnlistener *listener;
};

/* server alias list item. */
struct evhttp_server_alias {
	TAILQ_ENTRY(evhttp_server_alias) next;

	char *alias; /* the server alias. */
};

struct evhttp {
	/* Next vhost, if this is a vhost. */
	TAILQ_ENTRY(evhttp) next_vhost;

	/* All listeners for this host */
	TAILQ_HEAD(boundq, evhttp_bound_socket) sockets;

	TAILQ_HEAD(httpcbq, evhttp_cb) callbacks;

	/* All live HTTP connections on this host. */
	struct evconq connections;
	/* All live WebSockets sessions on this host. */
	struct evwsq ws_sessions;
	int connection_max;
	int connection_cnt;

	TAILQ_HEAD(vhostsq, evhttp) virtualhosts;

	TAILQ_HEAD(aliasq, evhttp_server_alias) aliases;

	/* NULL if this server is not a vhost */
	char *vhost_pattern;

	struct timeval timeout_read;		/* timeout for read */
	struct timeval timeout_write;		/* timeout for write */

	size_t default_max_headers_size;
	ev_uint64_t default_max_body_size;
	int flags;
	const char *default_content_type;

	/* Bitmask of all HTTP methods that we accept and pass to user
	 * callbacks. */
	ev_uint32_t allowed_methods;

	/* Fallback callback if all the other callbacks for this connection
	   don't match. */
	void (*gencb)(struct evhttp_request *req, void *);
	void *gencbarg;

	struct bufferevent* (*bevcb)(struct event_base *, void *);
	void *bevcbarg;
	int (*newreqcb)(struct evhttp_request *req, void *);
	void *newreqcbarg;

	int (*errorcb)(struct evhttp_request *, struct evbuffer *, int, const char *, void *);
	void *errorcbarg;

	struct event_base *base;

	evhttp_ext_method_cb ext_method_cmp;
};

/* XXX most of these functions could be static. */

/* resets the connection; can be reused for more requests */
void evhttp_connection_reset_(struct evhttp_connection *, int);

/* connects if necessary */
int evhttp_connection_connect_(struct evhttp_connection *);

enum evhttp_request_error;
/* notifies the current request that it failed; resets connection */
EVENT2_EXPORT_SYMBOL
void evhttp_connection_fail_(struct evhttp_connection *,
    enum evhttp_request_error error);

enum message_read_status;

EVENT2_EXPORT_SYMBOL
enum message_read_status evhttp_parse_firstline_(struct evhttp_request *, struct evbuffer*);
EVENT2_EXPORT_SYMBOL
enum message_read_status evhttp_parse_headers_(struct evhttp_request *, struct evbuffer*);

void evhttp_start_read_(struct evhttp_connection *);
void evhttp_start_write_(struct evhttp_connection *);

/* response sending HTML the data in the buffer */
void evhttp_response_code_(struct evhttp_request *, int, const char *);
void evhttp_send_page_(struct evhttp_request *, struct evbuffer *);

struct bufferevent * evhttp_start_ws_(struct evhttp_request *req);

/* [] has been stripped */
#define _EVHTTP_URI_HOST_HAS_BRACKETS 0x02

EVENT2_EXPORT_SYMBOL
int evhttp_decode_uri_internal(const char *uri, size_t length,
    char *ret, int decode_plus);

#endif /* HTTP_INTERNAL_H_INCLUDED_ */
