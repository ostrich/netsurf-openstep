/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <openssl/pem.h>
#include <openssl/x509v3.h>
#include "content/fetchers/curl-identity.h"

static int verify(X509_STORE *store, X509 *cert, const char *host, int fixed)
{
	X509_STORE_CTX *ctx = X509_STORE_CTX_new();
	X509_VERIFY_PARAM *param;
	int result;
	if (!ctx || X509_STORE_CTX_init(ctx, store, cert, NULL) != 1) exit(65);
	param = X509_STORE_CTX_get0_param(ctx);
	result = fixed ? fetch_curl_set_expected_identity(param, host, strlen(host)) :
		X509_VERIFY_PARAM_set1_host(param, host, strlen(host));
	if (result) result = X509_verify_cert(ctx);
	X509_STORE_CTX_free(ctx);
	return result == 1;
}
int main(int argc, char **argv)
{
	FILE *file;
	X509 *cert;
	X509_STORE *store;
	X509_VERIFY_PARAM *param;
	int failed = 0;
	if (argc != 3) return 64;
	file = fopen(argv[2], "r");
	if (!file) return 65;
	cert = PEM_read_X509(file, NULL, NULL, NULL);
	fclose(file);
	store = X509_STORE_new();
	param = X509_VERIFY_PARAM_new();
	if (!cert || !store || !param || X509_STORE_load_locations(store, argv[1], NULL) != 1) return 65;
#define CHECK(label, expression) do { int good = !!(expression); printf("IDENTITY %s %s\n",good?"PASS":"FAIL",label); if(!good)failed++; } while(0)
	CHECK("reproduce-IP-as-DNS-rejection", !verify(store, cert, "127.0.0.1", 0));
	CHECK("valid-IP-SAN", verify(store, cert, "127.0.0.1", 1));
	CHECK("valid-DNS-SAN", verify(store, cert, "fixture.test", 1));
	CHECK("wrong-IP-rejected", !verify(store, cert, "127.0.0.2", 1));
	CHECK("wrong-DNS-rejected", !verify(store, cert, "other.test", 1));
	CHECK("valid-IPv6-SAN", verify(store, cert, "[::1]", 1));
	CHECK("wrong-IPv6-rejected", !verify(store, cert, "[::2]", 1));
	CHECK("DNS-case-insensitive", verify(store, cert, "FIXTURE.TEST", 1));
	CHECK("second-IP-SAN", verify(store, cert, "10.0.2.2", 1));
	CHECK("numeric-DNS-is-not-IP", !verify(store, cert, "127.0.0.1.example", 1));
	CHECK("subdomain-is-not-parent", !verify(store, cert, "sub.fixture.test", 1));
	CHECK("null-host-rejected", !fetch_curl_set_expected_identity(param, NULL, 1));
	CHECK("oversized-IPv6-rejected", !fetch_curl_set_expected_identity(param,
		"[1111:1111:1111:1111:1111:1111:1111:1111:1111:1111]", 51));
	CHECK("empty-host-rejected", !fetch_curl_set_expected_identity(param, "", 0));
	CHECK("embedded-NUL-rejected", !fetch_curl_set_expected_identity(param, "a\0b", 3));
	CHECK("malformed-IPv6-rejected", !fetch_curl_set_expected_identity(param, "[bad", 4));
	X509_VERIFY_PARAM_free(param); X509_STORE_free(store); X509_free(cert);
	printf("IDENTITY-SUITE %d\n",failed);
	return failed != 0;
}
