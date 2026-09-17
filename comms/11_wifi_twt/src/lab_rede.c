/*
 * ARQUIVO DO CURSO (nrf-manaus-2) — nao existe no SDK.
 *
 * Pede a rede Wi-Fi no terminal serial (a console — uart30 na LM20-DK com a
 * EB II encaixada) e grava em settings, na storage_partition da placa. No boot
 * seguinte mostra o que tem gravado e da uma janela unica de JANELA_MS para
 * trocar; sem tecla, usa o gravado. Nao ha prompt periodico: cada campo e
 * pedido uma vez e so volta se a entrada for invalida.
 *
 * SSID e senha vao para a biblioteca wifi_credentials (backend settings), que
 * e de onde NET_REQUEST_WIFI_CONNECT_STORED le. IP e porta do servidor ficam
 * em "lab_rede/ip" e "lab_rede/porta", num handler proprio.
 *
 * Le por uart_poll_in() na console: nao precisa de UART assincrona nem de
 * shell, e convive com o printk/log que ja saem pela mesma UART.
 */

#include <errno.h>
#include <stdlib.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/net/net_ip.h>
#include <zephyr/net/wifi.h>
#include <zephyr/net/wifi_credentials.h>
#include <zephyr/settings/settings.h>
#include <zephyr/sys/printk.h>

#include "lab_rede.h"

#define JANELA_MS 5000
#define POLL_MS 10
#define LINHA_MAX (WIFI_PSK_MAX_LEN + 1)

static const struct device *const console = DEVICE_DT_GET(DT_CHOSEN(zephyr_console));

static struct {
	char ssid[WIFI_SSID_MAX_LEN + 1];
	char senha[WIFI_PSK_MAX_LEN + 1]; /* vazia = rede aberta */
	char ip[NET_IPV4_ADDR_LEN];
	uint16_t porta;
	bool pede_servidor;
} atual;

/* ------------------------------------------------ settings: IP e porta */

static int rede_set(const char *name, size_t len, settings_read_cb read_cb, void *cb_arg)
{
	const char *next;
	ssize_t n;

	if (settings_name_steq(name, "ip", &next) && !next) {
		if (len >= sizeof(atual.ip)) {
			return -EINVAL;
		}
		n = read_cb(cb_arg, atual.ip, sizeof(atual.ip) - 1);
		if (n < 0) {
			return (int)n;
		}
		atual.ip[n] = '\0';
		return 0;
	}

	if (settings_name_steq(name, "porta", &next) && !next) {
		if (len != sizeof(atual.porta)) {
			return -EINVAL;
		}
		n = read_cb(cb_arg, &atual.porta, sizeof(atual.porta));
		return n < 0 ? (int)n : 0;
	}

	return -ENOENT;
}

SETTINGS_STATIC_HANDLER_DEFINE(lab_rede, "lab_rede", NULL, rede_set, NULL, NULL);

/* --------------------------------------------------- credencial gravada */

static void copia_ssid(void *arg, const char *ssid, size_t ssid_len)
{
	char *dest = arg;

	if (dest[0] == '\0' && ssid_len <= WIFI_SSID_MAX_LEN) {
		memcpy(dest, ssid, ssid_len);
		dest[ssid_len] = '\0';
	}
}

/* true se havia uma rede gravada; preenche atual.ssid e atual.senha. */
static bool carrega_credencial(void)
{
	struct wifi_credentials_personal cred;

	atual.ssid[0] = '\0';
	atual.senha[0] = '\0';

	wifi_credentials_for_each_ssid(copia_ssid, atual.ssid);
	if (atual.ssid[0] == '\0') {
		return false;
	}

	if (wifi_credentials_get_by_ssid_personal_struct(atual.ssid, strlen(atual.ssid),
							 &cred) != 0) {
		atual.ssid[0] = '\0';
		return false;
	}

	if (cred.header.type == WIFI_SECURITY_TYPE_PSK &&
	    cred.password_len <= WIFI_PSK_MAX_LEN) {
		memcpy(atual.senha, cred.password, cred.password_len);
		atual.senha[cred.password_len] = '\0';
	}
	return true;
}

static int grava(void)
{
	enum wifi_security_type tipo =
		atual.senha[0] ? WIFI_SECURITY_TYPE_PSK : WIFI_SECURITY_TYPE_NONE;
	int ret;

	/* Uma rede so (WIFI_CREDENTIALS_MAX_ENTRIES=1): a nova substitui a antiga. */
	wifi_credentials_delete_all();
	ret = wifi_credentials_set_personal(atual.ssid, strlen(atual.ssid), tipo, NULL, 0,
					    atual.senha, strlen(atual.senha), 0,
					    WIFI_CHANNEL_ANY, 0);
	if (ret) {
		return ret;
	}

	if (atual.pede_servidor) {
		ret = settings_save_one("lab_rede/ip", atual.ip, strlen(atual.ip) + 1);
		if (ret) {
			return ret;
		}
		ret = settings_save_one("lab_rede/porta", &atual.porta, sizeof(atual.porta));
	}
	return ret;
}

/* ------------------------------------------------------------- console */

/* Espera ate `ms` por uma tecla. -1 se nao veio nenhuma. */
static int espera_tecla(int ms)
{
	int64_t fim = k_uptime_get() + ms;
	unsigned char c;

	while (k_uptime_get() < fim) {
		if (uart_poll_in(console, &c) == 0) {
			return c;
		}
		k_sleep(K_MSEC(POLL_MS));
	}
	return -1;
}

/* Le uma linha da console, ecoando, ate Enter. Aceita backspace. */
static void ler_linha(char *linha, size_t tamanho)
{
	static bool ultimo_foi_cr;
	size_t len = 0;
	unsigned char c;

	for (;;) {
		if (uart_poll_in(console, &c) < 0) {
			k_sleep(K_MSEC(POLL_MS));
			continue;
		}

		if (c == '\n' && ultimo_foi_cr) {
			/* O LF de um CR+LF: ja fechou a linha no CR. */
			ultimo_foi_cr = false;
			continue;
		}
		ultimo_foi_cr = (c == '\r');

		if (c == '\r' || c == '\n') {
			linha[len] = '\0';
			printk("\n");
			return;
		}

		if (c == '\b' || c == 0x7f) {
			if (len > 0) {
				len--;
				printk("\b \b");
			}
		} else if (c >= ' ' && c <= '~' && len < tamanho - 1) {
			/* So ASCII imprimivel: a abertura da porta no PC pode soltar
			 * um byte de lixo, que nao deve entrar na linha.
			 */
			linha[len++] = c;
			printk("%c", c);
		}
	}
}

static void pede_ssid(void)
{
	char linha[LINHA_MAX];

	for (;;) {
		printk("SSID da rede: ");
		ler_linha(linha, sizeof(linha));
		if (linha[0] != '\0' && strlen(linha) <= WIFI_SSID_MAX_LEN) {
			strcpy(atual.ssid, linha);
			return;
		}
		printk("SSID tem de 1 a %d caracteres.\n", WIFI_SSID_MAX_LEN);
	}
}

static void pede_senha(void)
{
	char linha[LINHA_MAX];
	size_t n;

	for (;;) {
		printk("Senha (Enter vazio = rede aberta): ");
		ler_linha(linha, sizeof(linha));
		n = strlen(linha);
		if (n == 0 || (n >= WIFI_PSK_MIN_LEN && n <= WIFI_PSK_MAX_LEN)) {
			strcpy(atual.senha, linha);
			return;
		}
		printk("Senha WPA2 tem de %d a %d caracteres.\n", WIFI_PSK_MIN_LEN,
		       WIFI_PSK_MAX_LEN);
	}
}

static void pede_servidor(uint16_t porta_padrao)
{
	char linha[LINHA_MAX];
	struct in_addr addr;
	unsigned long porta;
	char *fim;

	for (;;) {
		printk("IP do servidor no PC (ex.: 192.168.0.100): ");
		ler_linha(linha, sizeof(linha));
		if (net_addr_pton(AF_INET, linha, &addr) == 0) {
			strcpy(atual.ip, linha);
			break;
		}
		printk("IPv4 invalido.\n");
	}

	for (;;) {
		printk("Porta do servidor (Enter = %u): ", porta_padrao);
		ler_linha(linha, sizeof(linha));
		if (linha[0] == '\0') {
			atual.porta = porta_padrao;
			return;
		}
		porta = strtoul(linha, &fim, 10);
		if (*fim == '\0' && porta >= 1 && porta <= 65535) {
			atual.porta = (uint16_t)porta;
			return;
		}
		printk("Porta tem de ser um numero de 1 a 65535.\n");
	}
}

static void mostra_gravado(void)
{
	printk("\nRede gravada: \"%s\" (%s)", atual.ssid,
	       atual.senha[0] ? "com senha" : "aberta");
	if (atual.pede_servidor) {
		printk(", servidor %s:%u", atual.ip, atual.porta);
	}
	printk("\nEnter (ou nada em %d s) usa essa; qualquer outra tecla troca: ",
	       JANELA_MS / 1000);
}

/* ------------------------------------------------------------- publico */

void lab_rede_ler(bool pede_servidor_flag, uint16_t porta_padrao)
{
	bool gravado;
	int tecla;
	int ret;

	atual.pede_servidor = pede_servidor_flag;
	atual.ip[0] = '\0';
	atual.porta = 0;

	/* A wifi_credentials ja inicializou o settings no boot; aqui so o
	 * subtree deste modulo. settings_subsys_init() e idempotente.
	 */
	settings_subsys_init();
	settings_load_subtree("lab_rede");

	gravado = carrega_credencial();
	if (pede_servidor_flag && (atual.ip[0] == '\0' || atual.porta == 0)) {
		gravado = false;
	}

	printk("\n=== Rede Wi-Fi ===\n");
	if (gravado) {
		mostra_gravado();
		tecla = espera_tecla(JANELA_MS);
		if (tecla < 0 || tecla == '\r' || tecla == '\n') {
			printk("\nUsando a rede gravada.\n");
			return;
		}
		printk("\n");
	}

	for (;;) {
		pede_ssid();
		pede_senha();
		if (pede_servidor_flag) {
			pede_servidor(porta_padrao);
		}

		ret = grava();
		if (ret == 0) {
			break;
		}
		printk("Falha ao gravar em settings (%d); tente de novo.\n", ret);
	}

	printk("Gravado. Rede \"%s\"", atual.ssid);
	if (pede_servidor_flag) {
		printk(", servidor %s:%u", atual.ip, atual.porta);
	}
	printk(".\n");
}

const char *lab_rede_ssid(void)
{
	return atual.ssid;
}

const char *lab_rede_ip(void)
{
	return atual.ip;
}

uint16_t lab_rede_porta(void)
{
	return atual.porta;
}
