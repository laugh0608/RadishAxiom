//go:build linux && arm64

// The diskless G0 init mounts only kernel pseudo-filesystems and emits one report.
package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"slices"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

const (
	portName      = "org.radishaxiom.ax-b01.g0"
	kernelRelease = "6.18.60-0-virt"
	reportFormat  = "radishaxiom-private-ax-b01-g0-boot-v1"
	maxReport     = 64 * 1024
)

var (
	portDevice = regexp.MustCompile(`^vport[0-9]{1,5}p[0-9]{1,5}$`)
	bootIDForm = regexp.MustCompile(`^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`)
	controller = regexp.MustCompile(`^[a-z][a-z0-9_]{0,31}$`)
)

type mount struct {
	path, fs string
	flags    uintptr
}

const readOnly = syscall.MS_RDONLY | syscall.MS_NOSUID | syscall.MS_NOEXEC

var mounts = []mount{
	{"/proc", "proc", readOnly | syscall.MS_NODEV},
	{"/sys", "sysfs", readOnly | syscall.MS_NODEV},
	{"/dev", "devtmpfs", readOnly},
	{"/sys/fs/cgroup", "cgroup2", readOnly | syscall.MS_NODEV},
}

type bootReport struct {
	Arch        string   `json:"arch"`
	BootID      string   `json:"boot_id"`
	Controllers []string `json:"controllers"`
	Device      string   `json:"device"`
	DeviceID    string   `json:"device_id"`
	Format      string   `json:"format"`
	Kernel      string   `json:"kernel"`
	Mounts      []string `json:"mounts"`
	Port        string   `json:"port"`
}

func readBounded(path string, limit int64) (string, error) {
	file, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer file.Close()
	data, err := io.ReadAll(io.LimitReader(file, limit+1))
	if err == nil && int64(len(data)) > limit {
		err = fmt.Errorf("read limit for %s", path)
	}
	return string(data), err
}

func mountAndCheck() ([]string, error) {
	for _, entry := range mounts {
		if err := syscall.Mount(entry.fs, entry.path, entry.fs, entry.flags, ""); err != nil {
			return nil, fmt.Errorf("mount %s: %w", entry.path, err)
		}
	}
	text, err := readBounded("/proc/self/mountinfo", 16*1024)
	if err != nil {
		return nil, err
	}
	return checkedMounts(text)
}

func checkedMounts(text string) ([]string, error) {
	matched := make(map[string]string, len(mounts))
	for _, line := range strings.Split(strings.TrimSuffix(text, "\n"), "\n") {
		left, right, ok := strings.Cut(line, " - ")
		fields, fs := strings.Fields(left), strings.Fields(right)
		if !ok || len(fields) < 6 || len(fs) < 3 {
			return nil, errors.New("invalid mountinfo record")
		}
		for _, expected := range mounts {
			if fields[4] != expected.path {
				continue
			}
			options := strings.Split(fields[5], ",")
			if matched[expected.path] != "" || fields[3] != "/" || fs[0] != expected.fs ||
				!slices.Contains(options, "ro") || !slices.Contains(options, "nosuid") ||
				!slices.Contains(options, "noexec") ||
				slices.Contains(options, "nodev") != (expected.flags&syscall.MS_NODEV != 0) {
				return nil, fmt.Errorf("mount identity or permissions: %s", expected.path)
			}
			matched[expected.path] = expected.path + ":" + expected.fs + ":ro"
		}
	}
	result := make([]string, 0, len(mounts))
	for _, expected := range mounts {
		if matched[expected.path] == "" {
			return nil, fmt.Errorf("mount missing: %s", expected.path)
		}
		result = append(result, matched[expected.path])
	}
	return result, nil
}

func loadTransport() error {
	fd, err := syscall.Open("/virtio_mmio.ko", syscall.O_RDONLY|syscall.O_CLOEXEC|syscall.O_NOFOLLOW, 0)
	if err != nil {
		return err
	}
	defer syscall.Close(fd)
	parameters := [1]byte{0}
	_, _, errno := syscall.Syscall(syscall.SYS_FINIT_MODULE, uintptr(fd), uintptr(unsafe.Pointer(&parameters[0])), 0)
	runtime.KeepAlive(&parameters)
	if errno != 0 {
		return fmt.Errorf("load fixed virtio_mmio: %w", errno)
	}
	return nil
}

func namedPort() (string, error) {
	class := "/sys/class/virtio-ports"
	dir, err := os.Open(class)
	if errors.Is(err, os.ErrNotExist) {
		return "", nil
	}
	if err != nil {
		return "", err
	}
	defer dir.Close()
	entries, err := dir.ReadDir(17)
	if err != nil && err != io.EOF {
		return "", err
	}
	if len(entries) > 16 {
		return "", errors.New("virtio port entry limit")
	}
	var found string
	for _, entry := range entries {
		if !portDevice.MatchString(entry.Name()) {
			return "", errors.New("unexpected entry in virtio port class")
		}
		name, err := readBounded(filepath.Join(class, entry.Name(), "name"), 128)
		if errors.Is(err, os.ErrNotExist) {
			continue
		}
		if err != nil {
			return "", err
		}
		if name == portName+"\n" {
			if found != "" {
				return "", errors.New("duplicate report port")
			}
			found = entry.Name()
		}
	}
	return found, nil
}

func deviceNumber(id uint64) string {
	major := ((id >> 8) & 0xfff) | ((id >> 32) & 0xfffff000)
	minor := (id & 0xff) | ((id >> 12) & 0xffffff00)
	return fmt.Sprintf("%d:%d", major, minor)
}

func openReportPort(deadline time.Time) (int, string, string, error) {
	for time.Now().Before(deadline) {
		name, err := namedPort()
		if err != nil {
			return -1, "", "", err
		}
		if name == "" {
			time.Sleep(20 * time.Millisecond)
			continue
		}
		declared, err := readBounded(filepath.Join("/sys/class/virtio-ports", name, "dev"), 32)
		if err != nil {
			return -1, "", "", err
		}
		fd, err := syscall.Open(filepath.Join("/dev", name),
			syscall.O_WRONLY|syscall.O_NONBLOCK|syscall.O_NOFOLLOW|syscall.O_CLOEXEC, 0)
		if err != nil {
			return -1, "", "", err
		}
		var actual syscall.Stat_t
		if err = syscall.Fstat(fd, &actual); err != nil || actual.Mode&syscall.S_IFMT != syscall.S_IFCHR ||
			declared != deviceNumber(actual.Rdev)+"\n" {
			syscall.Close(fd)
			return -1, "", "", errors.New("virtio character device identity mismatch")
		}
		return fd, name, deviceNumber(actual.Rdev), nil
	}
	return -1, "", "", errors.New("virtio report port deadline")
}

func unameField(field []int8) string {
	var result []byte
	for _, c := range field {
		if c == 0 {
			break
		}
		result = append(result, byte(c))
	}
	return string(result)
}

func checkedReport(mountRows []string) (bootReport, error) {
	var report bootReport
	var system syscall.Utsname
	if err := syscall.Uname(&system); err != nil {
		return report, err
	}
	arch, release := unameField(system.Machine[:]), unameField(system.Release[:])
	if arch != "aarch64" || release != kernelRelease {
		return report, errors.New("unexpected kernel or architecture")
	}
	bootID, err := readBounded("/proc/sys/kernel/random/boot_id", 64)
	bootID = strings.TrimSuffix(bootID, "\n")
	if err != nil || !bootIDForm.MatchString(bootID) || bootID == "00000000-0000-0000-0000-000000000000" {
		return report, errors.New("boot ID read or format")
	}
	control, err := readBounded("/sys/fs/cgroup/cgroup.controllers", 1024)
	if err != nil {
		return report, err
	}
	controllers := strings.Fields(control)
	slices.Sort(controllers)
	for index, name := range controllers {
		if !controller.MatchString(name) || (index > 0 && controllers[index-1] == name) {
			return report, errors.New("invalid cgroup controller list")
		}
	}
	if !slices.Contains(controllers, "memory") || !slices.Contains(controllers, "pids") {
		return report, errors.New("required cgroup controllers are absent")
	}
	return bootReport{Format: reportFormat, Arch: arch, Kernel: release, BootID: bootID,
		Port: portName, Mounts: mountRows, Controllers: controllers}, nil
}

func emit(deadline time.Time, fd int, data []byte) error {
	for len(data) > 0 && time.Now().Before(deadline) {
		n, err := syscall.Write(fd, data)
		if n > 0 {
			data = data[n:]
		}
		if err != nil && err != syscall.EINTR && err != syscall.EAGAIN {
			return err
		}
		if n <= 0 {
			time.Sleep(20 * time.Millisecond)
		}
	}
	if len(data) != 0 {
		return errors.New("virtio report write deadline")
	}
	return nil
}

func collect(deadline time.Time) error {
	if os.Getpid() != 1 || os.Getuid() != 0 || os.Geteuid() != 0 {
		return errors.New("expected Linux boot init")
	}
	mountRows, err := mountAndCheck()
	if err != nil {
		return err
	}
	if err = loadTransport(); err != nil {
		return err
	}
	report, err := checkedReport(mountRows)
	if err != nil {
		return err
	}
	fd, name, id, err := openReportPort(deadline)
	if err != nil {
		return err
	}
	defer syscall.Close(fd)
	report.Device, report.DeviceID = name, id
	raw, err := json.Marshal(report)
	if err != nil || len(raw)+1 > maxReport {
		return errors.New("report encoding or length")
	}
	return emit(deadline, fd, append(raw, '\n'))
}

func main() {
	if err := collect(time.Now().Add(8 * time.Second)); err != nil {
		fmt.Fprintln(os.Stderr, err)
	}
	_ = syscall.Reboot(syscall.LINUX_REBOOT_CMD_POWER_OFF)
	// PID 1 must remain present if the platform fails to power down.
	for {
		time.Sleep(time.Hour)
	}
}
