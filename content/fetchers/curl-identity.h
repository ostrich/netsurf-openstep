/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef NETSURF_CURL_IDENTITY_H
#define NETSURF_CURL_IDENTITY_H

#include <string.h>
#include <openssl/x509_vfy.h>

/* URL host components retain brackets around IPv6 literals. DNS and IP SANs
 * are distinct reference identifiers; do not require both for an IP URL.
 * Called once on the new per-handshake verification context. LibreSSL does
 * not support clearing an IP with set1_ip(NULL, 0); DNS contexts have none. */
static int fetch_curl_set_expected_identity(X509_VERIFY_PARAM *param,
		const char *host, size_t length)
{
	char literal[46];
	if (!host || !length || memchr(host, 0, length)) return 0;
	if (host[0] == '[') {
		if (length < 3 || host[length-1] != ']' || length-2 >= sizeof(literal)) return 0;
		memcpy(literal, host+1, length-2);
		literal[length-2] = 0;
		return X509_VERIFY_PARAM_set1_host(param, NULL, 0) &&
			X509_VERIFY_PARAM_set1_ip_asc(param, literal);
	}
	if (length < sizeof(literal)) {
		memcpy(literal, host, length);
		literal[length] = 0;
		/* Let the TLS library parse numeric dotted addresses, without adding
		 * an inet_pton dependency to platforms with older system libraries. */
		if (strspn(literal, "0123456789.") == length && strchr(literal, '.'))
			return X509_VERIFY_PARAM_set1_host(param, NULL, 0) &&
				X509_VERIFY_PARAM_set1_ip_asc(param, literal);
	}
	return X509_VERIFY_PARAM_set1_host(param, host, length);
}
#endif
