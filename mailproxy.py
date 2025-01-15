import asyncio
import configparser
import logging
import os
import smtplib
import sys
import email.parser

from aiosmtpd.controller import Controller
from aiosmtpd import _get_or_new_eventloop


__version__ = '1.0.2'

SERVER_LOG = logging.getLogger("server")

def configure_logging():
    stderr_handler = logging.StreamHandler(sys.stderr)
    logger = logging.getLogger("mail.log")
    fmt = "[%(asctime)s {%(filename)s:%(lineno)d} %(levelname)s] %(message)s"
    datefmt = None
    formatter = logging.Formatter(fmt, datefmt, "%")
    stderr_handler.setFormatter(formatter)
    logger.addHandler(stderr_handler)
    logger.setLevel(logging.INFO)
    SERVER_LOG.addHandler(stderr_handler)
    SERVER_LOG.setLevel(logging.INFO)


class MailProxyHandler:
    def __init__(self,
                 host,
                 port=0,
                 auth=None,
                 use_ssl=False,
                 starttls=False,
                 internal_domains='',
                 header_name=None,
                 header_value=None):
        self._host = host
        self._port = port
        auth = auth or {}
        self._auth_user = auth.get('user')
        self._auth_password = auth.get('password')
        self._use_ssl = use_ssl
        self._starttls = starttls
        self._internal_domains = internal_domains.split(',')
        self._header_name = header_name
        self._header_value = header_value


    async def handle_DATA(self, server, session, envelope):
        parser = email.parser.BytesParser()
        headers = parser.parsebytes(envelope.content, headersonly=True)

        if self._header_name in headers and headers[self._header_name] == self._header_value:
            SERVER_LOG.info('Initial recipients: %s', envelope.rcpt_tos)
            self.update_recipients(envelope)
            SERVER_LOG.info('Final recipients: %s', envelope.rcpt_tos)

            if len(envelope.rcpt_tos) == 0:
                SERVER_LOG.info('All recipients were filtered out')
                return "553 Cannot send internal email to provided recipients"

        try:
            refused = self._deliver(envelope)
        except smtplib.SMTPRecipientsRefused as e:
            SERVER_LOG.info('Got SMTPRecipientsRefused: %s', refused)
            return "553 Recipients refused {}".format(' '.join(refused.keys()))
        except smtplib.SMTPResponseException as e:
            return "{} {}".format(e.smtp_code, e.smtp_error)
        else:
            if refused:
                SERVER_LOG.info('Recipients refused: %s', refused)
            return '250 OK'


    def update_recipients(self, envelope):
        """Removes all recipients except internal ones"""
        new_recipients = []
        for recipient in envelope.rcpt_tos:
            recipient_list = recipient.split('@')

            if len(recipient_list) < 2 or recipient_list[1] in self._internal_domains:
                new_recipients.append(recipient)

        envelope.rcpt_tos = new_recipients


    # adapted from https://github.com/aio-libs/aiosmtpd/blob/master/aiosmtpd/handlers.py
    def _deliver(self, envelope):
        refused = {}
        try:
            if self._use_ssl:
                s = smtplib.SMTP_SSL()
            else:
                s = smtplib.SMTP()
            s.connect(self._host, self._port)
            if self._starttls:
                s.starttls()
                s.ehlo()
            if self._auth_user and self._auth_password:
                s.login(self._auth_user, self._auth_password)
            try:
                refused = s.sendmail(
                    envelope.mail_from,
                    envelope.rcpt_tos,
                    envelope.original_content
                )
            finally:
                s.quit()
        except (OSError, smtplib.SMTPException) as e:
            SERVER_LOG.exception('got %s', e.__class__)
            # All recipients were refused. If the exception had an associated
            # error code, use it.  Otherwise, fake it with a SMTP 554 status code.
            errcode = getattr(e, 'smtp_code', 554)
            errmsg = getattr(e, 'smtp_error', e.__class__)
            raise smtplib.SMTPResponseException(errcode, errmsg.decode())


if __name__ == '__main__':
    configure_logging()

    if len(sys.argv) == 2:
        config_path = sys.argv[1]
    else:
        config_path = os.path.join(
            sys.path[0],
            'config.ini'
        )
    if not os.path.exists(config_path):
        raise Exception("Config file not found: {}".format(config_path))

    config = configparser.ConfigParser()
    config.read(config_path)

    use_auth = config.getboolean('remote', 'smtp_auth', fallback=False)
    if use_auth:
        auth = {
            'user': config.get('remote', 'smtp_auth_user'),
            'password': config.get('remote', 'smtp_auth_password')
        }
    else:
        auth = None

    loop = _get_or_new_eventloop()
    server = server_loop = None

    controller = Controller(
        MailProxyHandler(
            host=config.get('remote', 'host'),
            port=config.getint('remote', 'port', fallback=25),
            auth=auth,
            use_ssl=config.getboolean('remote', 'use_ssl',fallback=False),
            starttls=config.getboolean('remote', 'starttls',fallback=False),
            internal_domains=config.get('filter', 'internal_domains', fallback=''),
            header_name=config.get('filter', 'header_name', fallback=None),
            header_value=config.get('filter', 'header_value', fallback=None)
        ),
        hostname=config.get('local', 'host', fallback='127.0.0.1'),
        port=config.getint('local', 'port', fallback=25),
    )
    controller.start()
    try:
        input("Server started. Press Return to quit.\n")
        controller.stop()
    except EOFError:
        loop.run_forever()
