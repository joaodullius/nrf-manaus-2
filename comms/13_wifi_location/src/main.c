/* Codigo do curso (nrf-manaus-2) -- nao vem do SDK.
 *
 * Lab 13: conecta na rede da sala (esqueleto do lab 7/9), varre os pontos de
 * acesso Wi-Fi ao redor (NET_REQUEST_WIFI_SCAN) e manda a lista para o PC por
 * um socket TCP -- uma linha "AP,<bssid>,<rssi>,<frequencia_mhz>,<ssid>" por
 * ponto de acesso, seguida de "FIM". Quem resolve a posicao e o PC
 * (tools/wifi_locate.py), consultando os Location Services (Wi-Fi) do nRF
 * Cloud: o kit nunca sabe onde esta, so enxerga vizinhos.
 *
 * Faz um scan automatico assim que a conexao fica pronta e repete a cada
 * aperto do sw0 (sw3 nao existe com o shield nesta versao do SDK -- mesma
 * nota do lab 9).
 */
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/logging/log.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/net/socket.h>
#include <zephyr/net/net_if.h>
#include <zephyr/net/net_mgmt.h>
#include <zephyr/net/net_event.h>
#include <zephyr/net/wifi_mgmt.h>

#ifdef CONFIG_WIFI_READY_LIB
#include <net/wifi_ready.h>
#endif /* CONFIG_WIFI_READY_LIB */

LOG_MODULE_REGISTER(lab_wifi_location, CONFIG_LOG_DEFAULT_LEVEL);
#include "lab_rede.h"

/* sw3 nao existe com o shield nrf7002eb2 nesta versao do SDK (o overlay
 * apaga o botao e o alias): o botao do lab e o sw0, mesma nota do lab 9.
 */
#define SW0_NODE DT_ALIAS(sw0)
static const struct gpio_dt_spec botao = GPIO_DT_SPEC_GET(SW0_NODE, gpios);
static struct gpio_callback botao_cb_data;

static struct net_mgmt_event_callback wifi_cb;
static struct net_mgmt_event_callback net_cb;
static struct net_mgmt_event_callback scan_cb;

static K_SEM_DEFINE(ip_pronto, 0, 1);
static K_SEM_DEFINE(scan_pronto, 0, 1);
static K_SEM_DEFINE(scan_disparado, 0, 1);

/* Um AP capturado no scan, ja no formato textual que sai na linha para o PC
 * -- convertido dentro do callback (handler_scan_result(), abaixo), nao
 * guardado como struct wifi_scan_result crua: essa struct e valida so
 * durante o callback (o driver reaproveita o buffer logo depois).
 */
struct ap_encontrado {
	char bssid[sizeof("xx:xx:xx:xx:xx:xx")];
	int8_t rssi;
	uint16_t freq_mhz;
	char ssid[WIFI_SSID_MAX_LEN + 1];
};

/* Uma varredura real desta bancada viu 25 redes (ver o relatorio da task);
 * 32 da folga sem gastar memoria a toa. Excedentes sao descartados com
 * aviso, nao travam o scan.
 */
#define MAX_APS 32

static struct ap_encontrado aps[MAX_APS];
static size_t num_aps;
static K_MUTEX_DEFINE(aps_mutex);

/* Converte canal+banda (o que struct wifi_scan_result carrega) para
 * frequencia em MHz (o que o formato de linha deste lab manda, e o que a
 * ferramenta de PC guarda em "frequency" -- so para a lista impressa; o
 * nRF Cloud so usa macAddress/signalStrength). Formulas do proprio Zephyr,
 * so invertidas (wifi_freq_to_channel(), subsys/net/l2/wifi/wifi_shell.c).
 */
static uint16_t canal_para_freq_mhz(enum wifi_frequency_bands band, uint8_t canal)
{
	switch (band) {
	case WIFI_FREQ_BAND_2_4_GHZ:
		return (canal == 14) ? 2484 : (uint16_t)(2407 + canal * 5);
	case WIFI_FREQ_BAND_5_GHZ:
		return (uint16_t)(5000 + canal * 5);
	default:
		/* O nRF7002 e dual-band (2,4/5 GHz) e nunca emite
		 * WIFI_FREQ_BAND_6_GHZ num scan -- sem caso real para validar
		 * uma formula, essa banda fica so no default (0).
		 */
		return 0;
	}
}

static void formatar_bssid(const uint8_t *mac, uint8_t mac_len, char *saida, size_t tam)
{
	if (mac_len < 6) {
		saida[0] = '\0';
		return;
	}
	snprintf(saida, tam, "%02x:%02x:%02x:%02x:%02x:%02x",
		 mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
}

static void handler_scan_result(struct net_mgmt_event_callback *cb)
{
	const struct wifi_scan_result *entry = (const struct wifi_scan_result *)cb->info;
	struct ap_encontrado novo = {0};
	size_t ssid_len;

	formatar_bssid(entry->mac, entry->mac_length, novo.bssid, sizeof(novo.bssid));
	novo.rssi = entry->rssi;
	novo.freq_mhz = canal_para_freq_mhz(entry->band, entry->channel);

	ssid_len = MIN(entry->ssid_length, sizeof(novo.ssid) - 1);
	memcpy(novo.ssid, entry->ssid, ssid_len);
	novo.ssid[ssid_len] = '\0';

	k_mutex_lock(&aps_mutex, K_FOREVER);
	if (num_aps < MAX_APS) {
		aps[num_aps++] = novo;
	} else {
		LOG_WRN("Descartando AP %s -- buffer de %d entradas cheio", novo.bssid, MAX_APS);
	}
	k_mutex_unlock(&aps_mutex);
}

static void handler_scan(struct net_mgmt_event_callback *cb, uint64_t evento,
			  struct net_if *iface)
{
	ARG_UNUSED(iface);

	if (evento == NET_EVENT_WIFI_SCAN_RESULT) {
		handler_scan_result(cb);
		return;
	}

	if (evento == NET_EVENT_WIFI_SCAN_DONE) {
		const struct wifi_status *status = (const struct wifi_status *)cb->info;

		if (status->status) {
			LOG_WRN("Scan terminou com erro (%d)", status->status);
		}
		k_sem_give(&scan_pronto);
	}
}

/* Pede o scan e espera terminar (via NET_EVENT_WIFI_SCAN_DONE, tratado em
 * handler_scan() acima). Zera o acumulado antes de pedir -- um scan novo
 * substitui o anterior, nunca soma em cima.
 */
static int solicitar_scan(void)
{
	struct net_if *iface = net_if_get_first_wifi();
	struct wifi_scan_params params = {0};

	if (!iface) {
		LOG_ERR("Nenhuma interface Wi-Fi encontrada");
		return -ENODEV;
	}

	k_mutex_lock(&aps_mutex, K_FOREVER);
	num_aps = 0;
	k_mutex_unlock(&aps_mutex);

	if (net_mgmt(NET_REQUEST_WIFI_SCAN, iface, &params, sizeof(params))) {
		LOG_ERR("Pedido de scan Wi-Fi falhou");
		return -EIO;
	}

	LOG_INF("Scan solicitado...");

	if (k_sem_take(&scan_pronto, K_SECONDS(30)) < 0) {
		LOG_ERR("Tempo esgotado esperando o scan terminar");
		return -ETIMEDOUT;
	}

	return 0;
}

/* Reimplementacao enxuta do padrao de socket TCP ja usado no lab 9
 * (comms/09_wifi_tcp/src/transporte.c): abre, manda, fecha -- sem conexao
 * persistente nem thread de recepcao, porque este lab so manda dados, nunca
 * recebe comando de volta. Cada scan e uma conexao nova.
 */
static int mandar_scan_para_pc(void)
{
	struct net_sockaddr_in endereco = {0};
	char linha[96];
	size_t i;
	int sock;
	int ret;

	sock = zsock_socket(NET_AF_INET, NET_SOCK_STREAM, 0);
	if (sock < 0) {
		LOG_ERR("Falha ao criar o socket (%d)", -errno);
		return -errno;
	}

	endereco.sin_family = NET_AF_INET;
	endereco.sin_port = net_htons(lab_rede_porta());

	ret = net_addr_pton(NET_AF_INET, lab_rede_ip(), &endereco.sin_addr);
	if (ret < 0) {
		LOG_ERR("IP do servidor invalido: %s", lab_rede_ip());
		zsock_close(sock);
		return ret;
	}

	ret = zsock_connect(sock, (struct net_sockaddr *)&endereco, sizeof(endereco));
	if (ret < 0) {
		ret = -errno;
		LOG_ERR("Falha ao conectar em %s:%d (%d)",
			lab_rede_ip(), lab_rede_porta(), ret);
		zsock_close(sock);
		return ret;
	}

	k_mutex_lock(&aps_mutex, K_FOREVER);
	for (i = 0; i < num_aps; i++) {
		int n = snprintf(linha, sizeof(linha), "AP,%s,%d,%u,%s\n",
				  aps[i].bssid, aps[i].rssi, aps[i].freq_mhz, aps[i].ssid);
		if (n > 0) {
			zsock_send(sock, linha, (size_t)n, 0);
		}
	}
	ret = (int)num_aps;
	k_mutex_unlock(&aps_mutex);

	zsock_send(sock, "FIM\n", 4, 0);
	zsock_close(sock);

	LOG_INF("Scan (%d AP(s)) enviado para %s:%d", ret,
		lab_rede_ip(), lab_rede_porta());
	return 0;
}

static void realizar_scan_e_enviar(void)
{
	if (solicitar_scan() < 0) {
		return;
	}
	mandar_scan_para_pc();
}

static void thread_scan(void)
{
	while (1) {
		k_sem_take(&scan_disparado, K_FOREVER);
		realizar_scan_e_enviar();
	}
}

/* Rede (net_mgmt do scan, socket TCP): mesmo piso de 3072 medido no lab 9
 * para threads que fazem rede -- ver o relatorio da task.
 */
K_THREAD_DEFINE(scan_id, 3072, thread_scan, NULL, NULL, NULL, 7, 0, -1);

static void botao_pressionado_cb(const struct device *dev, struct gpio_callback *cb,
				  uint32_t pins)
{
	ARG_UNUSED(dev);
	ARG_UNUSED(cb);
	ARG_UNUSED(pins);

	k_sem_give(&scan_disparado);
}

static void configurar_botao(void)
{
	int ret;

	if (!gpio_is_ready_dt(&botao)) {
		LOG_ERR("Botao sw0 nao esta pronto");
		return;
	}

	ret = gpio_pin_configure_dt(&botao, GPIO_INPUT);
	if (ret < 0) {
		LOG_ERR("Falha ao configurar o botao sw0 (%d)", ret);
		return;
	}

	ret = gpio_pin_interrupt_configure_dt(&botao, GPIO_INT_EDGE_TO_ACTIVE);
	if (ret < 0) {
		LOG_ERR("Falha ao configurar a interrupcao do botao sw0 (%d)", ret);
		return;
	}

	gpio_init_callback(&botao_cb_data, botao_pressionado_cb, BIT(botao.pin));
	gpio_add_callback(botao.port, &botao_cb_data);
}

static void handler_wifi(struct net_mgmt_event_callback *cb, uint64_t evento,
			  struct net_if *iface)
{
	ARG_UNUSED(iface);

	if (evento != NET_EVENT_WIFI_CONNECT_RESULT) {
		return;
	}

	const struct wifi_status *status = (const struct wifi_status *)cb->info;

	if (status->status) {
		LOG_ERR("Falha ao conectar ao Wi-Fi (%d)", status->status);
	} else {
		LOG_INF("Conectado ao Wi-Fi");
	}
}

static void handler_net(struct net_mgmt_event_callback *cb, uint64_t evento,
			 struct net_if *iface)
{
	ARG_UNUSED(iface);

	if (evento != NET_EVENT_IPV4_DHCP_BOUND) {
		return;
	}

	const struct net_if_dhcpv4 *dhcpv4 = cb->info;
	char ip[NET_IPV4_ADDR_LEN];

	net_addr_ntop(NET_AF_INET, &dhcpv4->requested_ip, ip, sizeof(ip));
	LOG_INF("IP obtido por DHCP: %s", ip);

	k_sem_give(&ip_pronto);
}

#ifdef CONFIG_WIFI_READY_LIB
/* O supplicant (wpa_supplicant) demora um instante depois do driver do
 * nRF7002 inicializar. Pedir conexao antes disso falha com -ENOTSUP (-134) --
 * mesmo padrao do lab 7 (comms/07_wifi_sta/src/main.c) e do lab 9
 * (comms/09_wifi_tcp/src/main.c), reproduzido aqui.
 */
static K_SEM_DEFINE(wifi_pronto_sem, 0, 1);
static bool wifi_esta_pronto;

static void wifi_ready_cb(bool pronto)
{
	wifi_esta_pronto = pronto;
	k_sem_give(&wifi_pronto_sem);
}

static int esperar_wifi_pronto(void)
{
	wifi_ready_callback_t cb = {
		.wifi_ready_cb = wifi_ready_cb,
	};
	struct net_if *iface = net_if_get_first_wifi();
	int ret;

	if (!iface) {
		LOG_ERR("Nenhuma interface Wi-Fi encontrada");
		return -ENODEV;
	}

	ret = register_wifi_ready_callback(cb, iface);
	if (ret < 0) {
		LOG_ERR("Falha ao registrar o callback de Wi-Fi pronto (%d)", ret);
		return ret;
	}

	LOG_INF("Aguardando o supplicant do Wi-Fi ficar pronto...");
	ret = k_sem_take(&wifi_pronto_sem, K_SECONDS(10));
	if (ret < 0) {
		LOG_ERR("Tempo esgotado esperando o Wi-Fi ficar pronto (%d)", ret);
		return ret;
	}
	if (!wifi_esta_pronto) {
		LOG_ERR("Wi-Fi nao ficou pronto");
		return -EIO;
	}

	return 0;
}
#endif /* CONFIG_WIFI_READY_LIB */

static int conectar_wifi(void)
{
	struct net_if *iface = net_if_get_first_wifi();

	if (!iface) {
		LOG_ERR("Nenhuma interface Wi-Fi encontrada");
		return -ENODEV;
	}

	if (net_mgmt(NET_REQUEST_WIFI_CONNECT_STORED, iface, NULL, 0)) {
		LOG_ERR("Pedido de conexao Wi-Fi falhou");
		return -EIO;
	}

	LOG_INF("Conexao Wi-Fi solicitada");
	return 0;
}

int main(void)
{
	/* CURSO: rede da sala e IP/porta do servidor, digitados no terminal e
	 * gravados em settings. So retorna com tudo valido.
	 */
	lab_rede_ler(true, lab_rede_porta());

	net_mgmt_init_event_callback(&wifi_cb, handler_wifi, NET_EVENT_WIFI_CONNECT_RESULT);
	net_mgmt_add_event_callback(&wifi_cb);

	net_mgmt_init_event_callback(&net_cb, handler_net, NET_EVENT_IPV4_DHCP_BOUND);
	net_mgmt_add_event_callback(&net_cb);

	net_mgmt_init_event_callback(&scan_cb, handler_scan,
				      NET_EVENT_WIFI_SCAN_RESULT | NET_EVENT_WIFI_SCAN_DONE);
	net_mgmt_add_event_callback(&scan_cb);

	configurar_botao();

#ifdef CONFIG_WIFI_READY_LIB
	if (esperar_wifi_pronto() < 0) {
		LOG_WRN("Seguindo sem confirmar que o supplicant esta pronto");
	}
#endif /* CONFIG_WIFI_READY_LIB */

	if (conectar_wifi() < 0) {
		return -EIO;
	}

	LOG_INF("Aguardando IP por DHCP...");
	k_sem_take(&ip_pronto, K_FOREVER);

	k_thread_start(scan_id);

	/* Primeiro scan automatico, assim que a conexao fica pronta; os
	 * seguintes vem do sw0 (botao_pressionado_cb() -> thread_scan()).
	 */
	k_sem_give(&scan_disparado);

	return 0;
}
