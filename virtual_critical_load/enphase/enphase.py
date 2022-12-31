import json
import requests
import urllib3

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Union

urllib3.disable_warnings()


@dataclass(frozen=True)
class EnphaseToken:
    token: str
    generation_time: str
    expires_at: str

    @property
    def value(self) -> str:
        return self.token

    @property
    def start(self) -> datetime:
        try:
            return datetime.fromtimestamp(int(self.generation_time))
        except (TypeError, ValueError):
            raise Exception("Error converting `generation_time` to datetime.")

    @property
    def end(self) -> datetime:
        try:
            return datetime.fromtimestamp(int(self.expires_at))
        except (TypeError, ValueError):
            raise Exception("Error converting `expires_at` to datetime.")

    def validity(self) -> str:
        if self.token and self.generation_time and self.expires_at:
            return f"Token is valid between {self.start.isoformat()} and {self.end.isoformat()}. ({(self.end - self.start).days} days)"
        else:
            raise Exception("Cannot check validity; missing one of `token`, `generation_time`, `expires_at`.")

    def is_valid(self) -> bool:
        if self.generation_time and self.expires_at:
            return self.start <= datetime.now() <= self.end
        else:
            raise Exception("Cannot check is_valid; missing one of `generation_time`, `expires_at`.")


@dataclass
class EnphaseConfig:
    username: str
    password: str
    serial: str
    envoy: str
    site_id: str


@dataclass
class Enphase:
    envoy_ssl_verify: Optional[bool] = True

    _config: EnphaseConfig = None

    _token: Optional[EnphaseToken] = None
    _envoy_session: Optional[requests.Session] = None

    @property
    def config(self) -> EnphaseConfig:
        return self._config

    @config.setter
    def config(self, config: Union[dict, EnphaseConfig]):
        if isinstance(config, dict):
            self._config = EnphaseConfig(**config)
        elif isinstance(config, EnphaseConfig):
            self._config = config
        else:
            raise Exception("Enphase config provided is of unknown type.")

    def save(self):
        with open("enphase.config", mode="w") as f:
            f.write(json.dumps({
                "config": self._config.__dict__,
                "token": self._token.__dict__
            }))

    def load(self):
        with open("enphase.config", mode="r") as f:
            d = json.loads(f.read())
            d_config = d.get("config")
            d_token = d.get("token")

            self.config = d_config
            self._token = EnphaseToken(**d_token)

            if not self._token.is_valid():
                self.get_new_token()
                self.save()

    def get_new_token(self) -> EnphaseToken:
        if not self._config.username and not self._config.password and not self._config.serial:
            raise Exception("Username, password and envoy serial number are required.")

        session = requests.Session()

        login_url = "https://enlighten.enphaseenergy.com/login/login"
        login_response = session.post(url=login_url, data={
            "user[email]": self._config.username,
            "user[password]": self._config.password
        })

        token_url = f"https://enlighten.enphaseenergy.com/entrez-auth-token?serial_num={self._config.serial}"
        token_response = session.get(url=token_url)
        self._token = EnphaseToken(**json.loads(token_response.text))
        return self._token

    @property
    def token(self):
        return self._token

    def create_envoy_session(self) -> requests.Session:
        if not self._envoy_session:
            session = requests.Session()
            url = f"https://{self._config.envoy}/auth/check_jwt"
            headers = {"Authorization": f"Bearer {self._token.value}"}
            session.get(url=url, headers=headers, verify=self.envoy_ssl_verify)
            self._envoy_session = session
        # expires = next(x for x in session.cookies if x.name == 'sessionId').expires
        return self._envoy_session

    def home_json(self) -> dict:
        session = self.create_envoy_session()
        url = f"https://{self._config.envoy}/home.json"
        response = session.get(url=url, verify=self.envoy_ssl_verify)
        return json.loads(response.text)

    def production_json(self, details: int = 1) -> dict:
        session = self.create_envoy_session()
        url = f"https://{self._config.envoy}/production.json"
        response = session.get(url=url, params={'details': details}, verify=self.envoy_ssl_verify)
        return json.loads(response.text)

    def api_v1_production(self) -> dict:
        session = self.create_envoy_session()
        url = f"https://{self._config.envoy}/api/v1/production"
        response = session.get(url=url, verify=self.envoy_ssl_verify)
        return json.loads(response.text)

    def api_v1_production_inverters(self) -> dict:
        session = self.create_envoy_session()
        url = f"https://{self._config.envoy}/api/v1/production/inverters"
        response = session.get(url=url, verify=self.envoy_ssl_verify)
        return json.loads(response.text)

    def inventory_json(self, deleted: int = 1) -> dict:
        session = self.create_envoy_session()
        url = f"https://{self._config.envoy}/inventory.json"
        response = session.get(url=url, params={'deleted': deleted}, verify=self.envoy_ssl_verify)
        return json.loads(response.text)

    def ivp_ensemble_inventory(self) -> dict:
        session = self.create_envoy_session()
        url = f"https://{self._config.envoy}/ivp/ensemble/inventory"
        response = session.get(url=url, verify=self.envoy_ssl_verify)
        return json.loads(response.text)

    def ivp_meters(self) -> dict:
        session = self.create_envoy_session()
        url = f"https://{self._config.envoy}/ivp/meters"
        response = session.get(url=url, verify=self.envoy_ssl_verify)
        return json.loads(response.text)

    def admin_lib_network_display_json(self) -> dict:
        session = self.create_envoy_session()
        url = f"https://{self._config.envoy}/admin/lib/network_display.json"
        response = session.get(url=url, verify=self.envoy_ssl_verify)
        return json.loads(response.text)

    def admin_lib_dba_json(self) -> dict:
        session = self.create_envoy_session()
        url = f"https://{self._config.envoy}/admin/lib/dba.json"
        response = session.get(url=url, verify=self.envoy_ssl_verify)
        return json.loads(response.text)

    # def stream_meter(self):
    #     session = self.create_envoy_session()
    #     url = f"https://{self._config.envoy}/stream/meter"
    #     response = session.get(url=url, verify=False)
    #     return json.loads(response.text)

    def save_snapshot(self):
        snapshot = {}
        snapshot['home_json'] = self.home_json()
        snapshot['production_json'] = self.production_json()
        snapshot['api_v1_production'] = self.api_v1_production()
        snapshot['api_v1_production_invers'] = self.api_v1_production_inverters()
        snapshot['inventory_json'] = self.inventory_json()
        snapshot['ivp_ensemble_inventory'] = self.ivp_ensemble_inventory()
        snapshot['ivp_meters'] = self.ivp_meters()
        snapshot['admin_lib_network_display_json'] = self.admin_lib_network_display_json()
        snapshot['admin_lib_dba_json'] = self.admin_lib_dba_json()

        with open("enphase_snapshot.json", "w") as f:
            f.write(json.dumps(snapshot))


if __name__ == "__main__":
    # url = "https://httpbin.org/post"

    config = {
        "username": "nomb85@gmail.com",
        "password": "TpChYNRP*zvQ3uZ_u47zaQMse",
        "serial": "202234051232",
        "site_id": "3674932",
        "envoy": "envoy.local"
    }

    enphase = Enphase()
    enphase.envoy_ssl_verify = False
    enphase.load()

    # enphase.config = EnphaseConfig(**config)
    # enphase.get_new_token()
    # enphase.save()

    print(enphase.token.validity())
    print(f"is_valid: {enphase.token.is_valid()}.")

    # enphase.home_json()
    # enphase.ivp_ensemble_inventory()

    from pprint import pprint
    # pprint(enphase.api_v1_production_inverters())

    # enphase.save_snapshot()