/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Disposable loopback fixture. Never an installed service. */
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <openssl/ssl.h>
#include <openssl/err.h>

static int output(int fd, SSL *ssl, const char *data, int length)
{
	while (length > 0) {
		int n = ssl ? SSL_write(ssl, data, length) : (int)write(fd, data, length);
		if (n <= 0) return 0;
		data += n; length -= n;
	}
	return 1;
}
int main(int argc, char **argv)
{
	int listener, reuse = 1, port;
	struct sockaddr_in address;
	SSL_CTX *context = NULL;
	if (argc != 5) return 64;
	port = atoi(argv[1]);
	if (port < 1024 || port > 65535) return 64;
	signal(SIGPIPE, SIG_IGN);
	/* Both the outer runner and this process have bounded lifetimes. */
	alarm(300);
	if (strcmp(argv[2], "http") != 0) {
		SSL_library_init(); SSL_load_error_strings();
		context = SSL_CTX_new(TLS_server_method());
		if (!context || !SSL_CTX_set_min_proto_version(context, TLS1_2_VERSION) ||
			SSL_CTX_use_certificate_file(context, argv[3], SSL_FILETYPE_PEM) != 1 ||
			SSL_CTX_use_PrivateKey_file(context, argv[4], SSL_FILETYPE_PEM) != 1 ||
			SSL_CTX_check_private_key(context) != 1) { ERR_print_errors_fp(stderr); return 65; }
		if (strcmp(argv[2], "tls12") == 0) SSL_CTX_set_max_proto_version(context, TLS1_2_VERSION);
		if (strcmp(argv[2], "tls13") == 0) SSL_CTX_set_min_proto_version(context, TLS1_3_VERSION);
	}
	listener = socket(AF_INET, SOCK_STREAM, 0);
	memset(&address, 0, sizeof(address));
	address.sin_family = AF_INET;
	address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
	address.sin_port = htons(port);
	if (listener < 0 || setsockopt(listener, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse)) ||
		bind(listener, (struct sockaddr *)&address, sizeof(address)) || listen(listener, 8)) {
		perror("fixture listen"); return 66;
	}
	printf("SERVER READY %s %d\n", argv[2], port); fflush(stdout);
	for (;;) {
		int fd = accept(listener, NULL, NULL), count;
		SSL *ssl = NULL;
		char request[2048], path[256], header[512], body[2048];
		if (fd < 0) continue;
		if (context) {
			ssl = SSL_new(context);
			if (!ssl) { close(fd); continue; }
			SSL_set_fd(ssl, fd);
			if (SSL_accept(ssl) != 1) { SSL_free(ssl); close(fd); continue; }
		}
		count = ssl ? SSL_read(ssl, request, sizeof(request)-1) : (int)read(fd, request, sizeof(request)-1);
		if (count <= 0) goto done;
		request[count] = 0;
		if (sscanf(request, "GET %255s", path) != 1) goto done;
		printf("REQUEST %s %s\n", ssl ? SSL_get_version(ssl) : "HTTP", path); fflush(stdout);
		if (strcmp(path, "/redirect") == 0 || strcmp(path, "/loop") == 0) {
			sprintf(header, "HTTP/1.1 302 Found\r\nLocation: %s\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
				strcmp(path,"/loop") == 0 ? "/loop" : "/ok");
			output(fd, ssl, header, strlen(header));
		} else if (strcmp(path, "/large") == 0) {
			int offset;
			const char *headers = "HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n";
			output(fd, ssl, headers, strlen(headers));
			for (offset = 0; offset < 131072; offset += 1024) {
				int i;
				for (i = 0; i < 1024; i++) body[i] = 65 + (offset+i) % 26;
				if (!output(fd, ssl, "400\r\n", 5) || !output(fd, ssl, body, 1024) || !output(fd, ssl, "\r\n", 2)) break;
			}
			output(fd, ssl, "0\r\n\r\n", 5);
		} else {
			int missing = strcmp(path, "/missing") == 0;
			if (strncmp(path, "/page", 5) == 0 || strncmp(path, "/secure", 7) == 0) {
				const char *title = strncmp(path, "/secure", 7) == 0 ? "Secure browser check" : "Network browser check";
				sprintf(body, "<html><head><title>%s</title></head><body><h1>%s</h1><p id=\"js\">pending</p>"
					"<script>document.getElementById('js').textContent='JavaScript works';</script></body></html>", title, title);
			} else strcpy(body, missing ? "not-found\n" : "fixture-ok\n");
			sprintf(header, "HTTP/1.1 %s\r\nContent-Type: text/html\r\nContent-Length: %lu\r\nConnection: close\r\n\r\n",
				missing ? "404 Not Found" : "200 OK", (unsigned long)strlen(body));
			output(fd, ssl, header, strlen(header)); output(fd, ssl, body, strlen(body));
		}
	done:
		if (ssl) { SSL_shutdown(ssl); SSL_free(ssl); }
		close(fd);
	}
}
