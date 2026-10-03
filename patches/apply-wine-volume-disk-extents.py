from pathlib import Path

path = Path("/tmp/wine-src/dlls/ntdll/unix/file.c")
text = path.read_text()

old_include = """#ifdef HAVE_LINUX_IOCTL_H
#include <linux/ioctl.h>
#endif
"""
new_include = """#ifdef HAVE_LINUX_IOCTL_H
#include <linux/ioctl.h>
#include <linux/fs.h>
#endif
"""
if old_include not in text:
    raise SystemExit("Wine include anchor not found")
text = text.replace(old_include, new_include, 1)

anchor = """    ULONG device = (code >> 16);
    NTSTATUS status = STATUS_NOT_SUPPORTED;

"""
insert = """    ULONG device = (code >> 16);
    NTSTATUS status = STATUS_NOT_SUPPORTED;

    /*
     * Backblaze Personal 10.x verifies fixed drives using
     * IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS. Raw DOS device mappings such as
     * dosdevices/d:: -> /dev/loop0 are handled through ntdll's Unix-file path,
     * so this request never reaches mountmgr.sys and otherwise falls through
     * to STATUS_NOT_SUPPORTED.
     *
     * Mirror mountmgr's current single-extent behavior for a Unix-backed raw
     * device. Keep this deliberately narrow so every other IOCTL follows
     * Wine's normal code path.
     */
    if (code == IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS)
    {
        VOLUME_DISK_EXTENTS *extents = out_buffer;
        ULONGLONG bytes = 0;
        int fd, needs_close;
        struct stat st;

        if (!io || !out_buffer) return STATUS_INVALID_PARAMETER;
        if (out_size < sizeof(*extents)) return STATUS_BUFFER_TOO_SMALL;

        status = server_get_unix_fd( handle, 0, &fd, &needs_close, NULL, NULL );
        if (status) return status;

#ifdef linux
        if (ioctl( fd, BLKGETSIZE64, &bytes ) == -1)
#endif
        {
            if (!fstat( fd, &st ) && S_ISREG( st.st_mode )) bytes = st.st_size;
        }

        if (needs_close) close( fd );

        memset( extents, 0, sizeof(*extents) );
        extents->NumberOfDiskExtents = 1;
        extents->Extents[0].DiskNumber = 0;
        extents->Extents[0].StartingOffset.QuadPart = 0;
        extents->Extents[0].ExtentLength.QuadPart = bytes;
        io->Status = STATUS_SUCCESS;
        io->Information = sizeof(*extents);
        return STATUS_SUCCESS;
    }

"""
if anchor not in text:
    raise SystemExit("NtDeviceIoControlFile anchor not found")
text = text.replace(anchor, insert, 1)

path.write_text(text)
print("Applied Wine IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS compatibility shim")
