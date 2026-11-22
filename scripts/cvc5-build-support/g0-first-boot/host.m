#import <Foundation/Foundation.h>
#import <Security/Security.h>
#import <Virtualization/Virtualization.h>

#include <CommonCrypto/CommonDigest.h>
#include <fcntl.h>
#include <grp.h>
#include <limits.h>
#include <mach/mach_time.h>
#include <mach-o/dyld.h>
#include <membership.h>
#include <pwd.h>
#include <signal.h>
#include <sys/acl.h>
#include <sys/stat.h>
#include <sys/sysctl.h>
#include <unistd.h>

#include "boot-pins.h"

static NSString *const Root = @"/private/var/db/radishaxiom/ax-b01-g0";
static NSString *const PortName = @"org.radishaxiom.ax-b01.g0";
static NSString *const CommandLine = @"rdinit=/init panic=0 quiet";
static NSString *const MachineID = @"YnBsaXN0MDDRAQJUVVVJRE8QEIAxIHCCC0o4iGr5IRvgwnIICxAAAAAAAAABAQAAAAAAAAADAAAAAAAAAAAAAAAAAAAAIw==";
static const char *const Account = "_raxcg0";
enum { GuestMiB = 512, WorkSeconds = 65, TotalSeconds = 90,
       ReportLimit = 64 * 1024, ReceiptLimit = 256 * 1024 };
static volatile sig_atomic_t cancelled;

static _Noreturn void die(const char *reason) {
    fprintf(stderr, "%s\n", reason);
    exit(1);
}

static NSData *JSON(id value) {
    return [NSJSONSerialization dataWithJSONObject:value
        options:NSJSONWritingSortedKeys | NSJSONWritingWithoutEscapingSlashes error:NULL];
}

static BOOL matches(NSString *pattern, id value) {
    if (![value isKindOfClass:NSString.class]) return NO;
    NSRange found = [value rangeOfString:pattern options:NSRegularExpressionSearch];
    return found.location == 0 && found.length == [value length];
}

static BOOL validReport(NSData *raw) {
    if (raw.length < 2 || raw.length > ReportLimit) return NO;
    const unsigned char *bytes = raw.bytes;
    if (bytes[raw.length - 1] != '\n') return NO;
    NSData *body = [raw subdataWithRange:NSMakeRange(0, raw.length - 1)];
    id parsed = [NSJSONSerialization JSONObjectWithData:body options:0 error:NULL];
    if (![parsed isKindOfClass:NSDictionary.class]) return NO;
    NSDictionary *row = parsed;
    if (row.count != 9 || ![row[@"format"] isEqual:@"radishaxiom-private-ax-b01-g0-boot-v1"] ||
        ![row[@"arch"] isEqual:@"aarch64"] || ![row[@"kernel"] isEqual:@"6.18.60-0-virt"] ||
        ![row[@"port"] isEqual:PortName] ||
        !matches(@"vport[0-9]{1,5}p[0-9]{1,5}", row[@"device"]) ||
        !matches(@"[1-9][0-9]{0,9}:(0|[1-9][0-9]{0,9})", row[@"device_id"]) ||
        !matches(@"[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}", row[@"boot_id"]) ||
        [row[@"boot_id"] isEqual:@"00000000-0000-0000-0000-000000000000"] ||
        ![row[@"mounts"] isEqual:@[@"/proc:proc:ro", @"/sys:sysfs:ro", @"/dev:devtmpfs:ro",
                                @"/sys/fs/cgroup:cgroup2:ro"]]) return NO;
    id entries = row[@"controllers"];
    if (![entries isKindOfClass:NSArray.class] || [entries count] > 32 ||
        ![entries containsObject:@"pids"] || ![entries containsObject:@"memory"]) return NO;
    NSString *previous = nil;
    for (id name in entries) {
        if (!matches(@"[a-z][a-z0-9_]{0,31}", name) ||
            (previous && [previous compare:name options:NSLiteralSearch] != NSOrderedAscending)) return NO;
        previous = name;
    }
    // Read exactly one canonical record. This also rejects duplicate JSON keys and trailing bytes.
    return [body isEqualToData:JSON(row)];
}

static void requireMissingACL(int fd) {
    acl_t acl = acl_get_fd_np(fd, ACL_TYPE_EXTENDED);
    if (!acl) {
        if (errno != ENOENT) die("cannot establish path ACL");
        return;
    }
    acl_entry_t entry;
    int result = acl_get_entry(acl, ACL_FIRST_ENTRY, &entry);
    int saved = errno;
    acl_free(acl);
    if (result != -1 || saved != EINVAL) die("unexpected path ACL");
}

static int directoryAt(int parent, const char *name, uid_t uid, gid_t gid, mode_t mode) {
    int fd = openat(parent, name, O_RDONLY | O_NOFOLLOW | O_DIRECTORY | O_CLOEXEC);
    struct stat st;
    if (fd < 0 || fstat(fd, &st) != 0 || st.st_uid != uid || st.st_gid != gid ||
        (st.st_mode & 07777) != mode) die("directory absent or path ownership/mode mismatch");
    requireMissingACL(fd);
    return fd;
}

static int fileAt(int parent, const char *name, mode_t mode) {
    int fd = openat(parent, name, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
    struct stat st;
    if (fd < 0 || fstat(fd, &st) != 0 || !S_ISREG(st.st_mode) || st.st_nlink != 1 ||
        st.st_uid != 0 || st.st_gid != 0 || (st.st_mode & 07777) != mode)
        die("boot file absent or file ownership/mode/link mismatch");
    requireMissingACL(fd);
    return fd;
}

static void pinnedBytes(int fd, off_t size, const char *expected) {
    struct stat before, after;
    if (fd < 0 || fstat(fd, &before) != 0 || !S_ISREG(before.st_mode) || before.st_size != size)
        die("pinned input length or type mismatch");
    CC_SHA256_CTX context;
    CC_SHA256_Init(&context);
    unsigned char buffer[65536], digest[CC_SHA256_DIGEST_LENGTH];
    off_t consumed = 0;
    while (consumed < size) {
        ssize_t n = read(fd, buffer, MIN((off_t)sizeof(buffer), size - consumed));
        if (n <= 0) die("cannot read pinned input");
        CC_SHA256_Update(&context, buffer, (CC_LONG)n);
        consumed += n;
    }
    CC_SHA256_Final(digest, &context);
    char hex[sizeof(digest) * 2 + 1];
    for (size_t i = 0; i < sizeof(digest); ++i) snprintf(hex + i * 2, 3, "%02x", digest[i]);
    if (strcmp(hex, expected) || fstat(fd, &after) || before.st_size != after.st_size ||
        before.st_ctimespec.tv_sec != after.st_ctimespec.tv_sec ||
        before.st_ctimespec.tv_nsec != after.st_ctimespec.tv_nsec) die("pinned input identity mismatch");
}

static void checkHost(void) {
    char build[32];
    size_t size = sizeof(build);
    if (sysctlbyname("kern.osversion", build, &size, NULL, 0) != 0 || size != sizeof("26A434") ||
        strcmp(build, "26A434")) die("Darwin build mismatch");
    SecTaskRef task = SecTaskCreateFromSelf(kCFAllocatorDefault);
    if (!task) die("cannot identify executable entitlement");
    CFTypeRef value = SecTaskCopyValueForEntitlement(task, CFSTR("com.apple.security.virtualization"), NULL);
    BOOL entitled = value == kCFBooleanTrue;
    if (value) CFRelease(value);
    CFRelease(task);
    if (!entitled) die("virtualization entitlement absent");
}

static int protectedPaths(uid_t *uid, gid_t *gid) {
    struct passwd *identity = getpwnam(Account);
    if (!identity) die("dedicated execution account is absent");
    if (identity->pw_uid == 0 || strcmp(identity->pw_shell, "/usr/bin/false"))
        die("expected a noninteractive dedicated account");
    *uid = identity->pw_uid;
    *gid = identity->pw_gid;
    struct group *group = getgrnam(Account);
    gid_t supplementary[2];
    int count = getgroups(2, supplementary);
    if (!group || !*gid || group->gr_gid != *gid || getuid() != *uid || geteuid() != *uid ||
        getgid() != *gid || getegid() != *gid || count < 0 || count > 1 ||
        (count == 1 && supplementary[0] != *gid)) die("execution credentials mismatch");
    struct group *admin = getgrnam("admin");
    uuid_t accountUUID, adminUUID;
    int isAdmin = 0;
    if (!admin || mbr_uid_to_uuid(*uid, accountUUID) || mbr_gid_to_uuid(admin->gr_gid, adminUUID) ||
        mbr_check_membership(accountUUID, adminUUID, &isAdmin) || isAdmin) die("non-admin membership not established");
    int dir = directoryAt(AT_FDCWD, "/", 0, 0, 0755);
    for (const char *const *name = (const char *const[]){"private", "var", "db", "radishaxiom", "ax-b01-g0", NULL};
         *name; ++name) {
        int child = directoryAt(dir, *name, 0, 0, 0755);
        close(dir);
        dir = child;
    }
    int boot = directoryAt(dir, "boot", 0, 0, 0755);
    int self = fileAt(boot, "g0-first-boot", 0555);
    char executable[PATH_MAX];
    uint32_t length = sizeof(executable);
    if (_NSGetExecutablePath(executable, &length) != 0 ||
        strcmp(executable, "/private/var/db/radishaxiom/ax-b01-g0/boot/g0-first-boot"))
        die("launcher must enter through protected path");
    close(self);
    int kernel = fileAt(boot, "Image", 0444), initramfs = fileAt(boot, "initramfs.cpio.gz", 0444);
    pinnedBytes(kernel, KERNEL_BYTES, KERNEL_SHA256);
    pinnedBytes(initramfs, INITRAMFS_BYTES, INITRAMFS_SHA256);
    close(kernel);
    close(initramfs);
    close(boot);
    int records = directoryAt(dir, "records", *uid, *gid, 0700);
    close(dir);
    return records;
}

static VZVirtualMachineConfiguration *configurationFor(NSString *kernel, NSString *initramfs,
                                                       NSFileHandle *writeEnd) {
    VZLinuxBootLoader *loader = [[VZLinuxBootLoader alloc] initWithKernelURL:[NSURL fileURLWithPath:kernel]];
    loader.initialRamdiskURL = [NSURL fileURLWithPath:initramfs];
    loader.commandLine = CommandLine;
    VZVirtioConsolePortConfiguration *port = [[VZVirtioConsolePortConfiguration alloc] init];
    port.name = PortName;
    port.isConsole = NO;
    port.attachment = [[VZFileHandleSerialPortAttachment alloc] initWithFileHandleForReading:nil
                                                                      fileHandleForWriting:writeEnd];
    VZVirtioConsoleDeviceConfiguration *console = [[VZVirtioConsoleDeviceConfiguration alloc] init];
    console.ports.maximumPortCount = 1;
    console.ports[0] = port;
    NSData *machineData = [[NSData alloc] initWithBase64EncodedString:MachineID options:0];
    VZGenericMachineIdentifier *identity = [[VZGenericMachineIdentifier alloc] initWithDataRepresentation:machineData];
    if (!identity || ![identity.dataRepresentation isEqualToData:machineData]) die("invalid fixed machine identity");
    VZGenericPlatformConfiguration *platform = [[VZGenericPlatformConfiguration alloc] init];
    platform.machineIdentifier = identity;
    platform.nestedVirtualizationEnabled = NO;
    VZVirtualMachineConfiguration *config = [VZVirtualMachineConfiguration new];
    config.platform = platform;
    config.bootLoader = loader;
    config.CPUCount = 1;
    config.memorySize = GuestMiB * 1024ULL * 1024;
    config.consoleDevices = @[console];
    config.storageDevices = @[];
    config.networkDevices = @[];
    config.socketDevices = @[];
    config.directorySharingDevices = @[];
    config.serialPorts = @[];
    config.entropyDevices = @[];
    config.memoryBalloonDevices = @[];
    config.graphicsDevices = @[];
    config.audioDevices = @[];
    config.keyboards = @[];
    config.pointingDevices = @[];
    config.usbControllers = @[];
    config.customVirtioDevices = @[];
    return config;
}

static void checkConfiguration(VZVirtualMachineConfiguration *config, NSString *kernel,
                               NSString *initramfs, NSFileHandle *writeEnd) {
    VZLinuxBootLoader *loader = (VZLinuxBootLoader *)config.bootLoader;
    VZGenericPlatformConfiguration *platform = (VZGenericPlatformConfiguration *)config.platform;
    if (config.CPUCount != 1 || config.memorySize != GuestMiB * 1024ULL * 1024 ||
        ![loader.commandLine isEqual:CommandLine] || ![loader.kernelURL.path isEqual:kernel] ||
        ![loader.initialRamdiskURL.path isEqual:initramfs] || platform.isNestedVirtualizationEnabled ||
        ![[platform.machineIdentifier.dataRepresentation base64EncodedStringWithOptions:0] isEqual:MachineID] ||
        config.consoleDevices.count != 1) die("boot configuration readback mismatch");
    for (NSArray *devices in @[config.storageDevices, config.networkDevices, config.socketDevices,
        config.directorySharingDevices, config.serialPorts, config.entropyDevices, config.memoryBalloonDevices,
        config.graphicsDevices, config.audioDevices, config.keyboards, config.pointingDevices,
        config.usbControllers, config.customVirtioDevices]) {
        if (devices.count) die("unexpected auxiliary VM device");
    }
    VZVirtioConsoleDeviceConfiguration *console = (VZVirtioConsoleDeviceConfiguration *)config.consoleDevices[0];
    VZVirtioConsolePortConfiguration *port = console.ports[0];
    VZFileHandleSerialPortAttachment *attachment = (VZFileHandleSerialPortAttachment *)port.attachment;
    if (console.ports.maximumPortCount != 1 || ![port.name isEqual:PortName] || port.isConsole ||
        attachment.fileHandleForReading || attachment.fileHandleForWriting.fileDescriptor != writeEnd.fileDescriptor)
        die("one-way serial configuration readback mismatch");
}

static NSDictionary *plan(BOOL validated) {
    return @{@"appkit_or_console_tty": @NO, @"start_count": @1, @"vcpu": @1, @"guest_mib": @(GuestMiB),
             @"port": PortName, @"mac_to_guest": @NO, @"command_line": CommandLine, @"machine_id": MachineID,
             @"data_disks": @0, @"network_devices": @0, @"directory_shares": @0, @"socket_devices": @0,
             @"work_seconds": @(WorkSeconds), @"cleanup_seconds": @(TotalSeconds - WorkSeconds),
             @"overall_seconds": @(TotalSeconds), @"report_bytes": @(ReportLimit), @"receipt_bytes": @(ReceiptLimit),
             @"effective_account": @"_raxcg0", @"protected_root": Root, @"kernel_sha256": @KERNEL_SHA256,
             @"initramfs_sha256": @INITRAMFS_SHA256, @"configuration_validated": @(validated)};
}

@interface GuestStop : NSObject <VZVirtualMachineDelegate>
@property BOOL poweredOff;
@property BOOL failed;
@end

@implementation GuestStop
- (void)guestDidStopVirtualMachine:(VZVirtualMachine *)virtualMachine {
    (void)virtualMachine;
    self.poweredOff = YES;
}
- (void)virtualMachine:(VZVirtualMachine *)virtualMachine didStopWithError:(NSError *)error {
    (void)virtualMachine;
    (void)error;
    self.failed = YES;
}
@end

static double elapsed(uint64_t started) {
    mach_timebase_info_data_t scale;
    if (mach_timebase_info(&scale) != KERN_SUCCESS || !scale.denom) die("monotonic clock scale unavailable");
    return ((mach_continuous_time() - started) * (double)scale.numer / scale.denom) / 1e9;
}

static void onCancel(int signalNumber) { cancelled = signalNumber; }
static void onDeadline(int signalNumber) { (void)signalNumber; _exit(124); }

static void appendReceipt(int fd, NSDictionary *row) {
    NSData *data = JSON(row);
    off_t offset = lseek(fd, 0, SEEK_END);
    if (!data || offset < 0 || (uint64_t)offset + data.length + 1 > ReceiptLimit ||
        write(fd, data.bytes, data.length) != (ssize_t)data.length || write(fd, "\n", 1) != 1 || fsync(fd))
        die("cannot retain bounded attempt receipt");
}

static int runOnce(VZVirtualMachineConfiguration *config, NSPipe *pipe, int receipt, uint64_t started) {
    int reading = pipe.fileHandleForReading.fileDescriptor;
    int flags = fcntl(reading, F_GETFL);
    if (flags < 0 || fcntl(reading, F_SETFL, flags | O_NONBLOCK) != 0) die("cannot bound report reads");
    VZVirtualMachine *vm = [[VZVirtualMachine alloc] initWithConfiguration:config queue:dispatch_get_main_queue()];
    GuestStop *delegate = [GuestStop new];
    vm.delegate = delegate;
    if (cancelled || elapsed(started) >= WorkSeconds) {
        appendReceipt(receipt, @{@"outcome": @"stopped-before-start", @"execution_ready": @NO});
        return 1;
    }
    __block BOOL startOK = NO, startFailed = NO;
    [vm startWithCompletionHandler:^(NSError *error) { startOK = !error; startFailed = error != nil; }];
    NSMutableData *raw = [NSMutableData data];
    BOOL stopped = NO, eof = NO, overflow = NO, forced = NO, stopRequested = NO;
    NSString *failure = nil;
    while (elapsed(started) < TotalSeconds - 1) {
        @autoreleasepool {
            if (!eof && !overflow) {
                unsigned char bytes[4096];
                ssize_t n = read(reading, bytes, sizeof(bytes));
                if (n > 0) {
                    NSUInteger remaining = ReportLimit - raw.length;
                    [raw appendBytes:bytes length:MIN((NSUInteger)n, remaining)];
                    if ((NSUInteger)n > remaining) {
                        overflow = YES;
                        failure = failure ?: @"report-limit";
                    }
                }
                if (n == 0) eof = YES;
                if (n < 0 && errno != EAGAIN && errno != EINTR) failure = failure ?: @"read-error";
            }
            if ((delegate.poweredOff || delegate.failed || startFailed || stopRequested) &&
                vm && vm.state == VZVirtualMachineStateStopped) {
                stopped = YES;
                vm = nil;
                [pipe.fileHandleForWriting closeFile];
            }
            if (startFailed || delegate.failed) failure = failure ?: @"virtualization-error";
            if (cancelled) failure = failure ?: @"cancelled";
            if (elapsed(started) >= WorkSeconds) failure = failure ?: @"work-deadline";
            if (stopped && (eof || overflow) && (delegate.poweredOff || failure)) break;
            if (failure && vm.canStop && !stopRequested) {
                stopRequested = YES;
                forced = YES;
                [vm stopWithCompletionHandler:^(NSError *error) { if (error) delegate.failed = YES; }];
            }
            CFRunLoopRunInMode(kCFRunLoopDefaultMode, 0.02, false);
        }
    }
    BOOL success = !failure && startOK && delegate.poweredOff && stopped && eof && !forced && validReport(raw);
    appendReceipt(receipt, @{@"outcome": success ? @"boot-report-confirmed" : (failure ?: @"report-or-exit-unconfirmed"),
        @"vm_stopped": @(stopped), @"transport_eof": @(eof), @"forced_stop_requested": @(forced),
        @"report_base64": [raw base64EncodedStringWithOptions:0], @"execution_ready": @NO});
    return success ? 0 : 1;
}

int main(int argc, const char **argv) {
    @autoreleasepool {
        if (argc == 3 && !strcmp(argv[1], "--check-report")) {
            int fd = open(argv[2], O_RDONLY | O_NONBLOCK | O_NOFOLLOW | O_CLOEXEC);
            struct stat st;
            if (fd < 0 || fstat(fd, &st) || !S_ISREG(st.st_mode) || st.st_size > ReportLimit) return 2;
            NSFileHandle *handle = [[NSFileHandle alloc] initWithFileDescriptor:fd closeOnDealloc:YES];
            return validReport([handle readDataOfLength:ReportLimit + 1]) ? 0 : 2;
        }
        if (argc == 2 && !strcmp(argv[1], "--preflight-paths")) {
            uid_t uid;
            gid_t gid;
            close(protectedPaths(&uid, &gid));
            return 0;
        }
        BOOL offline = argc == 4 && !strcmp(argv[1], "--offline");
        BOOL run = argc == 2 && !strcmp(argv[1], "--run");
        if (!offline && !run) die("expected --offline Image initramfs.cpio.gz, --check-report file, --preflight-paths, or --run");
        checkHost();
        NSString *kernel = [Root stringByAppendingPathComponent:@"boot/Image"];
        NSString *initramfs = [Root stringByAppendingPathComponent:@"boot/initramfs.cpio.gz"];
        uid_t uid = 0;
        gid_t gid = 0;
        int records = -1;
        if (offline) {
            kernel = [NSString stringWithUTF8String:argv[2]];
            initramfs = [NSString stringWithUTF8String:argv[3]];
            if (!kernel.isAbsolutePath || !initramfs.isAbsolutePath) die("offline inputs require absolute paths");
            int image = open(argv[2], O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
            int ram = open(argv[3], O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
            pinnedBytes(image, KERNEL_BYTES, KERNEL_SHA256);
            pinnedBytes(ram, INITRAMFS_BYTES, INITRAMFS_SHA256);
            close(image);
            close(ram);
        } else {
            records = protectedPaths(&uid, &gid);
        }
        NSPipe *pipe = [NSPipe pipe];
        if (!pipe) die("cannot create serial report pipe");
        VZVirtualMachineConfiguration *config = configurationFor(kernel, initramfs, pipe.fileHandleForWriting);
        checkConfiguration(config, kernel, initramfs, pipe.fileHandleForWriting);
        NSError *error = nil;
        BOOL validated = [config validateWithError:&error];
        if (offline) {
            puts([[[NSString alloc] initWithData:JSON(plan(validated)) encoding:NSUTF8StringEncoding] UTF8String]);
        }
        if (!validated) {
            fprintf(stderr, "configuration validation: %s (%ld): %s\n", error.domain.UTF8String,
                    (long)error.code, (error.localizedFailureReason ?: error.localizedDescription).UTF8String);
            return 1;
        }
        if (offline) return 0;
        umask(0077);
        int receipt = openat(records, "first-boot.jsonl", O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
        if (receipt < 0) die("first-boot receipt already exists or cannot be created");
        appendReceipt(receipt, @{@"outcome": @"attempt-pending", @"uid": @(uid), @"gid": @(gid), @"plan": plan(YES)});
        if (fsync(records)) die("cannot preserve first-boot receipt directory entry");
        close(records);
        signal(SIGINT, onCancel);
        signal(SIGTERM, onCancel);
        signal(SIGHUP, onCancel);
        signal(SIGALRM, onDeadline);
        uint64_t started = mach_continuous_time();
        alarm(TotalSeconds);
        int outcome = runOnce(config, pipe, receipt, started);
        alarm(0);
        close(receipt);
        return outcome;
    }
}
