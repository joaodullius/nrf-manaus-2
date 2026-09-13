/*
 * Copyright (c) 2026 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

/* The flash copy of the log: its volume, the switch, and the shell commands
 * that operate it without exposing the file system.
 *
 * The file-system log backend (CONFIG_LOG_BACKEND_FS) only opens files under
 * CONFIG_LOG_BACKEND_FS_DIR; it never mounts anything. This mounts a LittleFS
 * volume on the Partition Manager's littlefs_storage partition at that path,
 * early enough that the boot messages still in the log buffer land in flash
 * too.
 *
 * Writing every log line wears the flash, so the copy is off by default and
 * only runs when a marker file exists on the volume. The marker survives
 * reboots and reflashes, which is the point: switch it on before a field run
 * with "log_flash on", off again afterwards with "log_flash off".
 *
 * The "log_flash" shell command also lists, dumps and erases the files, adds
 * a marker line to the log and sets the level of the flash copy alone (also
 * persisted on the volume). See
 * docs/common/flash_log.md. Built only with CONFIG_LOG_BACKEND_FS, see
 * overlay-log-flash.conf.
 */

#include <stdlib.h>
#include <string.h>
#include <zephyr/kernel.h>
#include <zephyr/init.h>
#include <zephyr/fs/fs.h>
#include <zephyr/fs/littlefs.h>
#include <zephyr/storage/flash_map.h>
#include <zephyr/logging/log.h>
#include <zephyr/logging/log_ctrl.h>
#include <zephyr/shell/shell.h>
#include <zephyr/sys/reboot.h>

LOG_MODULE_REGISTER(log_flash, CONFIG_LOG_DEFAULT_LEVEL);

#define MARKER_FILE CONFIG_LOG_BACKEND_FS_DIR "/enabled"
#define LEVEL_FILE CONFIG_LOG_BACKEND_FS_DIR "/level"
#define LOG_PREFIX CONFIG_LOG_BACKEND_FS_FILE_PREFIX
#define LOG_PREFIX_LEN (sizeof(LOG_PREFIX) - 1)

FS_LITTLEFS_DECLARE_DEFAULT_CONFIG(log_lfs_config);

static struct fs_mount_t log_lfs_mnt = {
	.type = FS_LITTLEFS,
	.fs_data = &log_lfs_config,
	.storage_dev = (void *)PARTITION_ID(littlefs_storage),
	.mnt_point = CONFIG_LOG_BACKEND_FS_DIR,
};

static bool mounted;
/* Once enabled, the backend holds its newest file open for the rest of the
 * boot; disabling does not close it. Deleting that file under it would send
 * the writes that follow to blocks nothing references, so "erase" reboots.
 */
static bool started_this_boot;
/* Level of the flash copy alone; the console keeps its own. Persisted in
 * LEVEL_FILE as a single digit, independently of the on/off marker, so a
 * kit set to INF for a long run stays at INF through reboots.
 */
static uint8_t flash_level = CONFIG_LOG_MAX_LEVEL;

static const struct log_backend *fs_backend(void)
{
	return log_backend_get_by_name("log_backend_fs");
}

static bool marker_present(void)
{
	struct fs_dirent entry;

	return fs_stat(MARKER_FILE, &entry) == 0;
}

static const char *level_name(uint8_t level)
{
	static const char *const names[] = { "none", "err", "wrn", "inf", "dbg" };

	return level < ARRAY_SIZE(names) ? names[level] : "?";
}

static void level_load(void)
{
	struct fs_file_t file;
	char digit;

	fs_file_t_init(&file);
	if (fs_open(&file, LEVEL_FILE, FS_O_READ) != 0) {
		return;
	}

	if (fs_read(&file, &digit, 1) == 1 && digit >= '1' && digit <= '4') {
		flash_level = digit - '0';
	}

	(void)fs_close(&file);
}

static int level_store(void)
{
	struct fs_file_t file;
	char digit = '0' + flash_level;
	int err;

	fs_file_t_init(&file);
	err = fs_open(&file, LEVEL_FILE, FS_O_CREATE | FS_O_WRITE | FS_O_TRUNC);
	if (err) {
		return err;
	}

	err = fs_write(&file, &digit, 1);
	(void)fs_close(&file);

	return err == 1 ? 0 : (err < 0 ? err : -EIO);
}

static void level_apply(const struct log_backend *backend)
{
	uint32_t count = log_src_cnt_get(Z_LOG_LOCAL_DOMAIN_ID);

	for (uint32_t i = 0; i < count; i++) {
		(void)log_filter_set(backend, Z_LOG_LOCAL_DOMAIN_ID, i, flash_level);
	}
}

static int copy_start(void)
{
	const struct log_backend *backend = fs_backend();

	if (backend == NULL) {
		return -ENODEV;
	}

	if (!log_backend_is_active(backend)) {
		log_backend_enable(backend, NULL, CONFIG_LOG_MAX_LEVEL);
		started_this_boot = true;
	}

	level_apply(backend);

	return 0;
}

static void copy_stop(void)
{
	const struct log_backend *backend = fs_backend();

	if (backend != NULL && log_backend_is_active(backend)) {
		log_backend_disable(backend);
	}
}

static bool copy_active(void)
{
	const struct log_backend *backend = fs_backend();

	return backend != NULL && log_backend_is_active(backend);
}

static int log_flash_init(void)
{
	struct fs_statvfs stat;
	int err;

	/* A blank partition is formatted on the first mount. */
	err = fs_mount(&log_lfs_mnt);
	if (err) {
		LOG_ERR("Log volume mount failed: %d, no flash log this run", err);
		return 0;
	}

	mounted = true;
	level_load();

	err = fs_statvfs(log_lfs_mnt.mnt_point, &stat);
	if (err == 0) {
		LOG_INF("Log volume at %s: %lu KiB free of %lu KiB",
			log_lfs_mnt.mnt_point,
			(unsigned long)(stat.f_bfree * stat.f_frsize / 1024),
			(unsigned long)(stat.f_blocks * stat.f_frsize / 1024));
	}

	if (marker_present()) {
		(void)copy_start();
		LOG_INF("Flash log enabled, level %s", level_name(flash_level));
	} else {
		LOG_INF("Flash log disabled, enable with: log_flash on");
	}

	return 0;
}

/* After the file system types are registered (POST_KERNEL), before any module
 * starts logging in earnest.
 */
SYS_INIT(log_flash_init, APPLICATION, 0);

#if defined(CONFIG_SHELL)

/* The log files, oldest first. The backend numbers them in order of creation
 * and only ever creates a higher number, so the numbers sort them.
 */
struct log_file {
	int num;
	size_t size;
};

static int log_file_num(const struct fs_dirent *entry)
{
	if (entry->type != FS_DIR_ENTRY_FILE ||
	    strncmp(entry->name, LOG_PREFIX, LOG_PREFIX_LEN) != 0) {
		return -1;
	}

	return atoi(entry->name + LOG_PREFIX_LEN);
}

static int cmp_log_file(const void *a, const void *b)
{
	return ((const struct log_file *)a)->num - ((const struct log_file *)b)->num;
}

/* Fill files[] with what is on the volume, sorted; returns the count. */
static int log_files_get(struct log_file *files, int max)
{
	struct fs_dir_t dir;
	struct fs_dirent entry;
	int count = 0;
	int err;

	fs_dir_t_init(&dir);
	err = fs_opendir(&dir, CONFIG_LOG_BACKEND_FS_DIR);
	if (err) {
		return err;
	}

	while (count < max && fs_readdir(&dir, &entry) == 0 && entry.name[0] != '\0') {
		int num = log_file_num(&entry);

		if (num < 0) {
			continue;
		}

		files[count].num = num;
		files[count].size = entry.size;
		count++;
	}

	(void)fs_closedir(&dir);

	qsort(files, count, sizeof(files[0]), cmp_log_file);

	return count;
}

static void log_file_path(char *buf, size_t len, int num)
{
	snprintf(buf, len, "%s/%s%04d", CONFIG_LOG_BACKEND_FS_DIR, LOG_PREFIX, num);
}

/* Print a file to the shell as is. Returns the bytes printed, or an error. */
static int dump_file(const struct shell *sh, int num)
{
	char path[64];
	char buf[257];
	struct fs_file_t file;
	int total = 0;
	int err;

	log_file_path(path, sizeof(path), num);

	fs_file_t_init(&file);
	err = fs_open(&file, path, FS_O_READ);
	if (err) {
		return err;
	}

	while (true) {
		ssize_t n = fs_read(&file, buf, sizeof(buf) - 1);

		if (n < 0) {
			err = n;
			break;
		}
		if (n == 0) {
			break;
		}

		buf[n] = '\0';
		shell_fprintf(sh, SHELL_NORMAL, "%s", buf);
		total += n;
	}

	(void)fs_close(&file);

	return err ? err : total;
}

static int cmd_on(const struct shell *sh, size_t argc, char **argv)
{
	struct fs_file_t file;
	int err;

	if (!mounted) {
		shell_error(sh, "log volume is not mounted");
		return -ENODEV;
	}

	fs_file_t_init(&file);
	err = fs_open(&file, MARKER_FILE, FS_O_CREATE | FS_O_WRITE);
	if (err) {
		shell_error(sh, "cannot create %s: %d", MARKER_FILE, err);
		return err;
	}
	(void)fs_close(&file);

	err = copy_start();
	if (err) {
		shell_error(sh, "cannot enable the backend: %d", err);
		return err;
	}

	shell_print(sh, "flash log on, stays on across reboots");

	return 0;
}

static int cmd_off(const struct shell *sh, size_t argc, char **argv)
{
	int err;

	copy_stop();

	if (!mounted) {
		return 0;
	}

	err = fs_unlink(MARKER_FILE);
	if (err && err != -ENOENT) {
		shell_error(sh, "cannot remove %s: %d", MARKER_FILE, err);
		return err;
	}

	shell_print(sh, "flash log off, the files are kept");

	return 0;
}

static int cmd_status(const struct shell *sh, size_t argc, char **argv)
{
	struct fs_statvfs stat;

	shell_print(sh, "volume: %s", mounted ? "mounted" : "not mounted");
	shell_print(sh, "flash log: %s", copy_active() ? "on" : "off");
	shell_print(sh, "level: %s", level_name(flash_level));
	shell_print(sh, "file in use: %s", started_this_boot ? "yes" : "no");

	if (mounted && fs_statvfs(log_lfs_mnt.mnt_point, &stat) == 0) {
		shell_print(sh, "space: %lu KiB free of %lu KiB",
			    (unsigned long)(stat.f_bfree * stat.f_frsize / 1024),
			    (unsigned long)(stat.f_blocks * stat.f_frsize / 1024));
	}

	return 0;
}

static int cmd_ls(const struct shell *sh, size_t argc, char **argv)
{
	struct log_file files[CONFIG_LOG_BACKEND_FS_FILES_LIMIT];
	size_t total = 0;
	int count;

	if (!mounted) {
		shell_error(sh, "log volume is not mounted");
		return -ENODEV;
	}

	count = log_files_get(files, ARRAY_SIZE(files));
	if (count < 0) {
		shell_error(sh, "cannot read the volume: %d", count);
		return count;
	}

	for (int i = 0; i < count; i++) {
		bool in_use = started_this_boot && (i == count - 1);

		shell_print(sh, "%8u  %s%04d%s", (unsigned int)files[i].size, LOG_PREFIX,
			    files[i].num, in_use ? "  (in use)" : "");
		total += files[i].size;
	}

	shell_print(sh, "%d files, %u bytes", count, (unsigned int)total);

	return 0;
}

static int cmd_dump(const struct shell *sh, size_t argc, char **argv)
{
	struct log_file files[CONFIG_LOG_BACKEND_FS_FILES_LIMIT];
	size_t total = 0;
	int only = -1;
	int count;

	if (!mounted) {
		shell_error(sh, "log volume is not mounted");
		return -ENODEV;
	}

	if (argc > 1) {
		only = atoi(argv[1]);
	}

	count = log_files_get(files, ARRAY_SIZE(files));
	if (count < 0) {
		shell_error(sh, "cannot read the volume: %d", count);
		return count;
	}

	if (only >= 0) {
		int i;

		for (i = 0; i < count; i++) {
			if (files[i].num == only) {
				files[0] = files[i];
				break;
			}
		}
		if (i == count) {
			shell_error(sh, "no %s%04d", LOG_PREFIX, only);
			return -ENOENT;
		}
		count = 1;
	}

	for (int i = 0; i < count; i++) {
		total += files[i].size;
	}

	/* The markers let the host tell the dump apart from whatever else the
	 * console carried, and check that nothing was lost on the way.
	 */
	shell_print(sh, "===== DUMP BEGIN %d files %u bytes =====", count, (unsigned int)total);

	for (int i = 0; i < count; i++) {
		bool in_use = started_this_boot && only < 0 && (i == count - 1);
		int n;

		shell_print(sh, "===== %s%04d (%u bytes)%s =====", LOG_PREFIX, files[i].num,
			    (unsigned int)files[i].size, in_use ? " in use" : "");

		n = dump_file(sh, files[i].num);
		if (n < 0) {
			shell_print(sh, "===== read error %d =====", n);
		}
	}

	shell_print(sh, "===== DUMP END %d files %u bytes =====", count, (unsigned int)total);

	return 0;
}

static int cmd_erase(const struct shell *sh, size_t argc, char **argv)
{
	struct log_file files[CONFIG_LOG_BACKEND_FS_FILES_LIMIT];
	char path[64];
	int count;

	if (!mounted) {
		shell_error(sh, "log volume is not mounted");
		return -ENODEV;
	}

	/* Stop the writes first; the reboot below takes care of the file the
	 * backend may still hold open. The on/off marker is left alone.
	 */
	copy_stop();

	count = log_files_get(files, ARRAY_SIZE(files));
	if (count < 0) {
		shell_error(sh, "cannot read the volume: %d", count);
		return count;
	}

	for (int i = 0; i < count; i++) {
		int err;

		log_file_path(path, sizeof(path), files[i].num);
		err = fs_unlink(path);
		if (err) {
			shell_error(sh, "cannot remove %s: %d", path, err);
		}
	}

	shell_print(sh, "erased %d files, rebooting", count);
	k_sleep(K_MSEC(200));

	sys_reboot(SYS_REBOOT_COLD);

	return 0;
}

static int cmd_mark(const struct shell *sh, size_t argc, char **argv)
{
	char text[96] = "";
	size_t len = 0;

	for (size_t i = 1; i < argc; i++) {
		len += snprintf(text + len, sizeof(text) - len, "%s%s", i > 1 ? " " : "", argv[i]);
		if (len >= sizeof(text)) {
			break;
		}
	}

	LOG_INF("MARK: %s", text);
	shell_print(sh, "marked");

	return 0;
}

static int cmd_level(const struct shell *sh, size_t argc, char **argv)
{
	static const char *const names[] = { "err", "wrn", "inf", "dbg" };
	const struct log_backend *backend = fs_backend();

	for (size_t i = 0; i < ARRAY_SIZE(names); i++) {
		if (strcmp(argv[1], names[i]) != 0) {
			continue;
		}

		flash_level = LOG_LEVEL_ERR + i;
		if (backend != NULL && log_backend_is_active(backend)) {
			level_apply(backend);
		}

		if (mounted && level_store() != 0) {
			shell_warn(sh, "flash log level %s, but could not be saved", names[i]);
			return 0;
		}

		shell_print(sh, "flash log level %s, stays across reboots", names[i]);
		return 0;
	}

	shell_error(sh, "level is one of: err wrn inf dbg");

	return -EINVAL;
}

SHELL_STATIC_SUBCMD_SET_CREATE(sub_log_flash,
	SHELL_CMD(on, NULL, "Copy the log to flash, persistently", cmd_on),
	SHELL_CMD(off, NULL, "Stop copying the log to flash", cmd_off),
	SHELL_CMD(status, NULL, "State, level and space left", cmd_status),
	SHELL_CMD(ls, NULL, "List the log files", cmd_ls),
	SHELL_CMD_ARG(dump, NULL, "Print the log files, oldest first: dump [<number>]",
		      cmd_dump, 1, 1),
	SHELL_CMD(erase, NULL, "Delete every log file and reboot", cmd_erase),
	SHELL_CMD_ARG(mark, NULL, "Write a MARK line into the log: mark <text...>",
		      cmd_mark, 2, 16),
	SHELL_CMD_ARG(level, NULL, "Level of the flash copy alone, persistent: level err|wrn|inf|dbg",
		      cmd_level, 2, 0),
	SHELL_SUBCMD_SET_END
);

SHELL_CMD_REGISTER(log_flash, &sub_log_flash, "Flash copy of the log", NULL);

#endif /* CONFIG_SHELL */
