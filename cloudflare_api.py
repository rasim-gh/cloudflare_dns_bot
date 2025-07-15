import requests
from config import CLOUDFLARE_API_KEY, CLOUDFLARE_EMAIL

BASE_URL = "https://api.cloudflare.com/client/v4"

HEADERS = {
    "X-Auth-Email": CLOUDFLARE_EMAIL,
    "X-Auth-Key": CLOUDFLARE_API_KEY,
    "Content-Type": "application/json"
}

def get_zones():
    resp = requests.get(f"{BASE_URL}/zones", headers=HEADERS)
    if resp.status_code == 200:
        return resp.json()["result"]
    return []

def get_zone_info(domain_name):
    zones = get_zones()
    for zone in zones:
        if zone["name"] == domain_name:
            return zone
    return None

def get_zone_info_by_id(zone_id):
    resp = requests.get(f"{BASE_URL}/zones/{zone_id}", headers=HEADERS)
    if resp.status_code == 200:
        return resp.json()["result"]
    return None

def delete_zone(zone_id):
    resp = requests.delete(f"{BASE_URL}/zones/{zone_id}", headers=HEADERS)
    return resp.status_code == 200

def add_domain_to_cloudflare(domain_name):
    data = {
        "name": domain_name,
        "jump_start": True
    }
    resp = requests.post(f"{BASE_URL}/zones", headers=HEADERS, json=data)
    return resp.status_code == 200

def get_dns_records(zone_id):
    resp = requests.get(f"{BASE_URL}/zones/{zone_id}/dns_records", headers=HEADERS)
    if resp.status_code == 200:
        return resp.json()["result"]
    return []

def get_record_details(zone_id, record_id):
    resp = requests.get(f"{BASE_URL}/zones/{zone_id}/dns_records/{record_id}", headers=HEADERS)
    if resp.status_code == 200:
        return resp.json()["result"]
    return {}

def delete_dns_record(zone_id, record_id):
    resp = requests.delete(f"{BASE_URL}/zones/{zone_id}/dns_records/{record_id}", headers=HEADERS)
    return resp.status_code == 200

def create_dns_record(zone_id, type_, name, content, ttl=120, proxied=False):
    data = {
        "type": type_,
        "name": name,
        "content": content,
        "ttl": ttl,
        "proxied": proxied
    }
    resp = requests.post(f"{BASE_URL}/zones/{zone_id}/dns_records", headers=HEADERS, json=data)
    return resp.status_code == 200

def update_dns_record(zone_id, record_id, name, type_, content, ttl=120, proxied=False):
    data = {
        "type": type_,
        "name": name,
        "content": content,
        "ttl": ttl,
        "proxied": proxied
    }
    resp = requests.put(f"{BASE_URL}/zones/{zone_id}/dns_records/{record_id}", headers=HEADERS, json=data)
    return resp.status_code == 200

def toggle_proxied_status(zone_id, record_id):
    record = get_record_details(zone_id, record_id)
    if not record:
        return False
    new_status = not record.get("proxied", False)
    return update_dns_record(zone_id, record_id, record["name"], record["type"], record["content"], record["ttl"], new_status)
