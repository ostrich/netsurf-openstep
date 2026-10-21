/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Exercise the browser's actual curl/TLS build, with verification always on. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <curl/curl.h>

struct body { size_t length; int bad; int large; char text[128]; };
static size_t receive(char *data, size_t width, size_t count, void *context)
{
	struct body *body = context;
	size_t n = width * count, i;
	if (body->large) {
		for (i = 0; i < n; i++)
			if ((unsigned char)data[i] != 65 + (body->length + i) % 26) body->bad = 1;
	} else if (body->length + n < sizeof(body->text)) {
		memcpy(body->text + body->length, data, n);
		body->text[body->length + n] = 0;
	} else body->bad = 1;
	body->length += n;
	return n;
}

static int request(const char *label, const char *url, const char *ca,
		CURLcode expected, long status, int large, long version)
{
	CURL *curl = curl_easy_init();
	struct body body;
	CURLcode code;
	long response = 0;
	int good;
	if (!curl) return 1;
	memset(&body, 0, sizeof(body));
	body.large = large;
	curl_easy_setopt(curl, CURLOPT_URL, url);
	curl_easy_setopt(curl, CURLOPT_PROXY, "");
	curl_easy_setopt(curl, CURLOPT_CAINFO, ca);
	curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 1L);
	curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 2L);
	curl_easy_setopt(curl, CURLOPT_SSLVERSION, version);
	curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
	curl_easy_setopt(curl, CURLOPT_MAXREDIRS, 3L);
	curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT, 15L);
	curl_easy_setopt(curl, CURLOPT_TIMEOUT, 30L);
	curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, receive);
	curl_easy_setopt(curl, CURLOPT_WRITEDATA, &body);
	code = curl_easy_perform(curl);
	curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &response);
	good = code == expected;
	if (expected == CURLE_OK) {
		good = good && response == status && !body.bad;
		if (large) good = good && body.length == 131072;
		else good = good && strcmp(body.text, status == 404 ? "not-found\n" : "fixture-ok\n") == 0;
	}
	printf("NETWORK %s %s code=%d response=%ld bytes=%lu\n", good ? "PASS" : "FAIL",
		label, (int)code, response, (unsigned long)body.length);
	curl_easy_cleanup(curl);
	return !good;
}

int main(int argc, char **argv)
{
	FILE *config;
	char label[40], url[256];
	int error, large, status, failed = 0, cases = 0;
	long version;
	if (argc != 3 || curl_global_init(CURL_GLOBAL_DEFAULT) != CURLE_OK) return 64;
	printf("NETWORK LIBRARY %s\n", curl_version());
	config = fopen(argv[1], "r");
	if (!config) return 65;
	while (fscanf(config, "%39s %255s %d %d %d %ld", label, url, &error, &status, &large, &version) == 6) {
		failed += request(label, url, argv[2], (CURLcode)error, status, large, version);
		cases++;
	}
	if (!feof(config) || cases != 11) failed++;
	fclose(config);
	curl_global_cleanup();
	printf("NETWORK-SUITE %d cases=%d\n", failed, cases);
	return failed != 0;
}
