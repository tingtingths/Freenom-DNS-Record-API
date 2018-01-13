from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


class FreenomUrls:
    base = "https://my.freenom.com"
    client_area = "clientarea.php"
    login = "dologin.php"


class DNSRecord:

    def __init__(self, _id, name, ttl, type, value):
        self._id = _id
        self.name = name
        self.ttl = ttl
        self.type = type
        self.value = value

    def build_form(self):
        return {"records[{}][line]".format(self._id): "", "records[{}][type]".format(self._id): self.type,
                "records[{}][name]".format(self._id): self.name, "records[{}][ttl]".format(self._id): self.ttl,
                "records[{}][value]".format(self._id): self.value}


def get_external_ip():
    resp = requests.get("http://ipinfo.io").json()
    return resp["ip"]


def auth(email, passwd):
    headers = {
        "Origin": FreenomUrls.base,
        "Referer": urljoin(FreenomUrls.base, FreenomUrls.client_area)
    }
    r = requests.post(
        urljoin(FreenomUrls.base, FreenomUrls.login),
        verify=False,
        allow_redirects=False,
        data={"username": email, "password": passwd},
        headers=headers
    )
    # print("status: {}, headers: {}, cookies: {}".format(r.status_code, r.headers, r.cookies))

    ok = False
    if r.status_code == 302 and r.headers["Location"] == FreenomUrls.client_area:
        ok = True

    return ok, r.cookies


def get_dns(cookies_jar, id, domain):
    headers = {
        "Origin": FreenomUrls.base,
        "Referer": urljoin(FreenomUrls.base, FreenomUrls.client_area)
    }
    r = requests.get(
        urljoin(FreenomUrls.base, FreenomUrls.client_area),
        params={"domainid": id, "managedns": domain},
        cookies=cookies_jar,
        headers=headers,
        verify=False
    )
    # print("status: {}, headers: {}, cookies: {}".format(r.status_code, r.headers, r.cookies))

    soup = BeautifulSoup(r.text, "html.parser")

    if "loggedIn" not in soup.body["class"]:
        return None

    records = []
    i = 0
    for row in soup.form.table.tbody.find_all("tr"):
        record = DNSRecord(
            i,
            row.find(attrs={"name": "records[{}][name]".format(i)})["value"],
            int(row.find(attrs={"name": "records[{}][ttl]".format(i)})["value"]),
            row.find(attrs={"name": "records[{}][type]".format(i)})["value"],
            row.find(attrs={"name": "records[{}][value]".format(i)})["value"]
        )
        records.append(record)
        i += 1

    return records


def set_dns(cookies_jar, id, domain, records):
    # build payload
    data = {"dnsaction": "modify"}
    for record in records:
        data = {**data, **record.build_form()}

    headers = {
        "Origin": FreenomUrls.base,
        "Referer": urljoin(FreenomUrls.base, FreenomUrls.client_area)
    }
    r = requests.post(
        urljoin(FreenomUrls.base, FreenomUrls.client_area),
        data=data,
        params={"domainid": id, "managedns": domain},
        cookies=cookies_jar,
        headers=headers,
        verify=False
    )
    # print("status: {}, headers: {}, cookies: {}".format(r.status_code, r.headers, r.cookies))

    return r.status_code == 200


"""SAMPLE USAGE"""
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Update freenom dns records' IP.")
    parser.add_argument("last_known_ip", nargs="?",
                        help= \
                            "IP address to compare against external ip. " \
                            "If not provided, will always compare with the records' IP. " \
                            "Use this parameter as external cache to avoid needless operations."
                        )
    parser.add_argument("email", help="Freenom login email")
    parser.add_argument("passwd", help="Freenom login password")
    parser.add_argument("domain", help="Domain name")
    parser.add_argument("domain_id", help="Domain id")
    args = parser.parse_args()

    ext_ip = get_external_ip()

    if args.last_known_ip is not None and args.last_known_ip == ext_ip:
        print("External IP equals last known IP, nothing to be done...")
        print(ext_ip)
        exit()

    auth_ok, cookies = auth(args.email, args.passwd)

    if auth_ok:
        need_update = False
        records = get_dns(cookies, args.domain_id, args.domain)

        for r in records:
            if r.value != ext_ip:
                need_update = True
            r.value = ext_ip
            r.ttl = 14400 if r.name == "" else 7220

        if need_update:
            if set_dns(cookies, args.domain_id, args.domain, records):
                print("External IP NOT equals DNS IP, update successfully...")
                print(ext_ip)
            else:
                print("External IP NOT equals DNS IP, update failed...")
                print(ext_ip)
        else:
            print("External IP equals DNS IP, nothing to be done...")
            print(ext_ip)
