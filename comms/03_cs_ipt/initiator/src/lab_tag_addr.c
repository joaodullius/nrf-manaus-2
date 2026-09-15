/*
 * ARQUIVO DO CURSO (nrf-manaus-2) — nao existe no SDK.
 *
 * Pede o endereco BLE do TAG no terminal serial (a console, uart20 na LM20-DK)
 * a cada boot, antes do scan. Numa sala com varios TAGs anunciando o mesmo
 * UUID/nome, e o endereco que separa o seu do vizinho.
 *
 * Aceita "EC:EF:40:2D:5E:46", "EC:EF:40:2D:5E:46 random" e
 * "EC:EF:40:2D:5E:46 (random)" — o que se copia da linha "Identity:" do log
 * do TAG. Sem tipo, assume random. Invalido e recusado e o prompt volta.
 *
 * Le por uart_poll_in() na console: nao precisa de UART assincrona nem de
 * shell, e convive com o printk/log que ja saem pela mesma UART.
 */

#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/sys/printk.h>

#include "lab_tag_addr.h"

/* "EC:EF:40:2D:5E:46 (random)" + folga. */
#define LINE_SIZE 48
#define PROMPT_PERIOD_MS 5000
#define POLL_MS 10

static const struct device *const console = DEVICE_DT_GET(DT_CHOSEN(zephyr_console));

static int parse_tag_address(char *line, bt_addr_le_t *addr)
{
	char *value;
	char *type;
	char *save;

	value = strtok_r(line, " \t", &save);
	if (!value) {
		return -EINVAL;
	}

	type = strtok_r(NULL, " \t", &save);
	if (!type) {
		type = "random";
	} else {
		size_t n = strlen(type);

		if (n > 2 && type[0] == '(' && type[n - 1] == ')') {
			type[n - 1] = '\0';
			type++;
		}
	}

	return bt_addr_le_from_str(value, type, addr);
}

void lab_tag_addr_read(bt_addr_le_t *addr)
{
	char line[LINE_SIZE];
	char addr_str[BT_ADDR_LE_STR_LEN];
	size_t len = 0;
	bool prompt = true;
	int64_t last_prompt = 0;
	unsigned char c;

	for (;;) {
		if (prompt) {
			/* Repete tambem o que ja foi digitado, se houver. */
			line[len] = '\0';
			printk("\nEndereco BLE do tag (ex.: EC:EF:40:2D:5E:46 random): %s",
			       line);
			prompt = false;
			last_prompt = k_uptime_get();
		}

		if (uart_poll_in(console, &c) < 0) {
			k_sleep(K_MSEC(POLL_MS));
			if (k_uptime_get() - last_prompt >= PROMPT_PERIOD_MS) {
				prompt = true;
			}
			continue;
		}
		last_prompt = k_uptime_get();

		if (c == '\r' || c == '\n') {
			line[len] = '\0';

			if (len == 0) {
				/* Linha vazia (ou o LF de um CR+LF): ignora. */
			} else if (parse_tag_address(line, addr) == 0) {
				bt_addr_le_to_str(addr, addr_str, sizeof(addr_str));
				printk("\nProcurando o tag %s...\n", addr_str);
				return;
			} else {
				printk("\nEndereco invalido. Use o formato "
				       "EC:EF:40:2D:5E:46 random\n");
				prompt = true;
			}
			len = 0;
		} else if (c >= ' ' && c <= '~' && len < sizeof(line) - 1) {
			/* So ASCII imprimivel: a abertura da porta no PC pode soltar
			 * um byte de lixo, que nao deve entrar na linha.
			 */
			line[len++] = c;
			printk("%c", c);
		}
	}
}
