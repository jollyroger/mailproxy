# mailproxy
mailproxy is a simple SMTP proxy. It receives emails through an unencrypted,
unauthenticated SMTP interface and retransmits them through a remote SMTP
server that requires modern features such as encryption (SSL, STARTTLS) and/or
authentication (SMTP AUTH). mailproxy is primarily useful for enabling email
functionality in legacy software that only supports plain SMTP.

mailproxy can be used as a before-queue content filter for Postfix.
# Requirements
* Python 3.5+
* [aiosmtpd 1.1+](https://aiosmtpd.readthedocs.io)


# Usage
1. create and activate a virtualenv environment(`sudo apt install python3-virtualenv -y ;
   virtualenv venv ; . ./venv/bin/activate`)
2. Create a config file (see below).
3. Run mailproxy from the command line, e.g. `python mailproxy.py`.

By default, mailproxy looks for a `config.ini` in its own directory.
If you have placed your config file elsewhere, you can run mailproxy
using `python mailproxy.py <config_file_path>`.


# Configuration
An example config file for a mailproxy instance that accepts emails locally on port 25 for delivery via Gmail appears below:
```
[local]
host = 127.0.0.1
port = 25

[remote]
host = smtp.gmail.com
port = 465
use_ssl = yes
starttls = no
smtp_auth = yes
smtp_auth_user = USERNAME
smtp_auth_password = PASSWORD

[filter]
internal_domains = dev.box,dev.dev,mx.mydomain.com
header_name = X-Class
header_value = internal
```

The `[filter]` section allows to perform internal emails to be ent to
non-internal recipients. In above example, if an email has an `X-Class:
internal` SMTP Header, then all recipients that do not belong to internal
domains will be removed.

example command to test this:

    swaks \
        --server localhost:25 \
        --from user@mx.senkovych.com \
        --to to@example.com \
        --cc cc@example.com \
        --bcc bcc@example.com \
        --header-X-Class "internal"
