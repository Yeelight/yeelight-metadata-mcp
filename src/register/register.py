import socket
import time

import nacos

from config.config import settings
from log.logger import logger


class NacosRegistration:
    def __init__(self, **kwargs):
        self.logger = logger
        self.enable = kwargs.get("enable", True)
        if not self.enable:
            return
        self.nacos_server = kwargs.get("server")
        self.namespace = kwargs.get("namespace")
        self.service_name = kwargs.get("service-name", "undefined-service")
        ip = kwargs.get("ip")
        self.ip = ip or self.get_lan_ip()
        self.port = kwargs.get("port")
        self.weight = kwargs.get("weight", 1.0)
        self.cluster_name = kwargs.get("cluster-name", "DEFAULT")
        self.heartbeat_interval = kwargs.get("heartbeat-interval", 5)
        self.client = nacos.NacosClient(self.nacos_server, namespace=self.namespace)

    def get_lan_ip(self) -> str:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
        except Exception:
            ip = "127.0.0.1"
        finally:
            s.close()
        return ip

    def register_instance(self) -> bool:
        if not self.enable:
            logger.info("Nacos 注册功能未启用，不进行注册")
            return False

        try:
            self.client.add_naming_instance(
                service_name=self.service_name,
                ip=self.get_lan_ip(),
                port=self.port,
                enable=True,
                weight=self.weight,
                healthy=True,
                cluster_name=self.cluster_name,
                ephemeral=True,
                heartbeat_interval=self.heartbeat_interval,
            )
            logger.info(f"成功注册服务 {self.service_name} 到 Nacos")
            return True
        except Exception as e:
            self.logger.error(f"注册服务到 Nacos 失败: {str(e)}")
            return False

    def deregister_instance(self) -> bool:
        if not self.enable:
            logger.info("Nacos 注册功能未启用")
            return False

        try:
            self.client.remove_naming_instance(
                service_name=self.service_name,
                ip=self.get_lan_ip(),
                port=self.port,
                cluster_name=self.cluster_name,
            )
            logger.info(f"成功从 Nacos 注销服务 {self.service_name}")
            return True
        except Exception as e:
            logger.error(f"从 Nacos 注销服务失败: {str(e)}")
            return False


_nacos_registration_instance = None


def get_nacos_registration():
    global _nacos_registration_instance
    if _nacos_registration_instance is None:
        _nacos_registration_instance = NacosRegistration(**settings.NACOS_CONFIG)
    return _nacos_registration_instance


if __name__ == "__main__":
    registration = get_nacos_registration()
    registration.register_instance()
    time.sleep(60)
