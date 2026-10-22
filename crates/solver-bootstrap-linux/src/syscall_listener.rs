//! One listener delivery; ownership precedes protocol validation.
use super::*;
impl<K: Kernel> Linux<K> {
    pub(crate) fn receive_listener(&mut self, fd: i32) -> Result<OwnedFd> {
        let mut payload = [0u8; 8];
        let mut control = [0u64; 128];
        let iov = Iovec {
            base: payload.as_mut_ptr() as u64,
            len: 8,
        };
        let mut msg = MsgHdr {
            iov: &iov as *const _ as u64,
            iovlen: 1,
            control: control.as_mut_ptr() as u64,
            controllen: 1024,
            ..MsgHdr::default()
        };
        // SAFETY: all three nested buffers are live, correctly aligned and
        // exclusive output; recv uses DONTWAIT and CMSG_CLOEXEC, no retained ptr.
        let n = unsafe {
            self.call(
                "recvmsg-listener",
                Call {
                    nr: NR_RECVMSG,
                    args: [fd_arg(fd)?, &mut msg as *mut _ as u64, 0x40000040, 0, 0, 0],
                },
            )
        }?;
        // SAFETY: inspect initialized u64 storage as bytes (no uninit padding).
        let bytes = unsafe { core::slice::from_raw_parts(control.as_ptr().cast::<u8>(), 1024) };
        let mut received: [Option<OwnedFd>; 252] = core::array::from_fn(|_| None);
        let mut received_count = 0;
        let mut cursor = 0usize;
        let mut malformed = false;
        let end = usize::try_from(msg.controllen)
            .unwrap_or(usize::MAX)
            .min(1024);
        while cursor + 16 <= end {
            let len =
                u64::from_le_bytes(bytes[cursor..cursor + 8].try_into().expect("bounded cmsg"));
            let level = i32::from_le_bytes(
                bytes[cursor + 8..cursor + 12]
                    .try_into()
                    .expect("bounded cmsg"),
            );
            let kind = i32::from_le_bytes(
                bytes[cursor + 12..cursor + 16]
                    .try_into()
                    .expect("bounded cmsg"),
            );
            let len = match usize::try_from(len) {
                Ok(n) if n >= 16 && n <= end - cursor => n,
                _ => {
                    malformed = true;
                    break;
                }
            };
            if level == 1 && kind == 1 {
                if !(len - 16).is_multiple_of(4) {
                    malformed = true;
                }
                for value in bytes[cursor + 16..cursor + len].chunks_exact(4) {
                    let raw = i32::from_le_bytes(value.try_into().expect("four bytes"));
                    if raw < 0 || received_count >= received.len() {
                        malformed = true;
                        continue;
                    }
                    // SAFETY: each SCM_RIGHTS integer is a newly installed owned
                    // descriptor. Ownership is established BEFORE validation.
                    received[received_count] = Some(unsafe { OwnedFd::from_raw(raw) });
                    received_count += 1;
                }
            } else {
                malformed = true;
            }
            cursor += (len + 7) & !7;
        }
        let valid = !malformed
            && n == 8
            && payload == *LISTENER_RECORD
            && msg.flags & 0x28 == 0
            && msg.controllen == 24
            && cursor == 24
            && received_count == 1
            && bytes[..8] == 20u64.to_le_bytes()
            && bytes[20..24] == [0; 4];
        if valid {
            // No failure remains after moving the only received descriptor.
            return received[0]
                .take()
                .ok_or(Error::returned("listener-ownership"));
        }
        let mut cleanup_error = None;
        for owned in received.into_iter().flatten() {
            if let Err(e) = self.close(owned) {
                cleanup_error = Some(Error {
                    operation: "listener-record-rejected-cleanup-close",
                    kind: e.kind,
                });
            }
        }
        Err(cleanup_error.unwrap_or(Error::returned("listener-record")))
    }
}
