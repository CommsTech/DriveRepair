//! DriveRepair's small, std-only recovery core.
//!
//! This crate intentionally operates on REGULAR IMAGE FILES ONLY. Raw-device
//! writes, destructive sanitization and firmware access are not implemented.
//! Successful operating-system reads do NOT guarantee logical data correctness.

use std::fs::{self, File, OpenOptions};
use std::io::{self, Read, Seek, SeekFrom, Write};
use std::path::Path;
use std::time::UNIX_EPOCH;

pub mod firmware_inspect;

pub const VERSION: &str = "DRIVEREPAIR_IMAGE_MAP_V2";
pub const DEFAULT_CHUNK: usize = 1024 * 1024;

pub trait ReadAt {
    fn read_at(&mut self, offset: u64, output: &mut [u8]) -> io::Result<()>;
}
pub trait WriteAt {
    fn write_at(&mut self, offset: u64, data: &[u8]) -> io::Result<()>;
}
impl ReadAt for File {
    fn read_at(&mut self, offset: u64, output: &mut [u8]) -> io::Result<()> {
        self.seek(SeekFrom::Start(offset))?;
        self.read_exact(output)
    }
}
impl WriteAt for File {
    fn write_at(&mut self, offset: u64, data: &[u8]) -> io::Result<()> {
        self.seek(SeekFrom::Start(offset))?;
        self.write_all(data)
    }
}

/// A failed large read is retried in smaller pieces only during the second pass.
/// All fully readable pieces are copied; the enclosing chunk is only marked
/// complete if every byte was read. There is no invented reconstruction.
pub fn copy_region<S: ReadAt, D: WriteAt>(
    source: &mut S, destination: &mut D, offset: u64, length: usize,
    sector: usize, split_failures: bool, buffer: &mut Vec<u8>,
) -> io::Result<bool> {
    buffer.resize(length, 0);
    match source.read_at(offset, &mut buffer[..length]) {
        Ok(()) => {
            destination.write_at(offset, &buffer[..length])?;
            Ok(true)
        }
        Err(e) if matches!(e.kind(), io::ErrorKind::NotFound | io::ErrorKind::PermissionDenied) => Err(e),
        Err(_) if !split_failures || length <= sector => Ok(false),
        Err(_) => {
            let left = ((length / sector) / 2) * sector;
            if left == 0 || left == length {
                return Ok(false);
            }
            let lhs = copy_region(source, destination, offset, left, sector, true, buffer)?;
            let rhs = copy_region(source, destination, offset + left as u64,
                                  length - left, sector, true, buffer)?;
            Ok(lhs && rhs)
        }
    }
}

pub fn image_identity(path: &Path) -> io::Result<(String, u64, u128)> {
    let stat = fs::symlink_metadata(path)?;
    if !stat.file_type().is_file() {
        return Err(io::Error::new(io::ErrorKind::InvalidInput, "only regular, non-symlink files supported"));
    }
    let absolute = fs::canonicalize(path)?;
    let name = absolute.to_string_lossy().to_string();
    if name.contains('\n') || name.contains('\r') {
        return Err(io::Error::new(io::ErrorKind::InvalidInput, "newline in path unsupported"));
    }
    let modified = stat.modified()?.duration_since(UNIX_EPOCH).unwrap_or_default().as_nanos();
    Ok((name, stat.len(), modified))
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Map {
    pub source: String,
    pub source_size: u64,
    pub source_modified_ns: u128,
    pub chunk: usize,
    pub output_identity: String,
    // 0 = not attempted, 1 = all bytes copied and durable, 2 = missing bytes
    pub chunks: Vec<u8>,
}
impl Map {
    pub fn new(source: String, size: u64, stamp: u128, chunk: usize) -> io::Result<Self> {
        if size == 0 || !(512..=64 * 1024 * 1024).contains(&chunk) || chunk % 512 != 0 {
            return Err(io::Error::new(io::ErrorKind::InvalidInput, "invalid image size or chunk alignment"));
        }
        let count = size.div_ceil(chunk as u64);
        if count > 100_000_000 {
            return Err(io::Error::new(io::ErrorKind::InvalidInput, "image too large for this chunk size"));
        }
        Ok(Self { source, source_size: size, source_modified_ns: stamp, chunk, output_identity: String::new(),
                  chunks: vec![0; count as usize] })
    }
    pub fn header(&self) -> String {
        format!("{}\n{}\n{}\n{}\n{}\n{}\n", VERSION, self.source,
                self.source_size, self.source_modified_ns, self.chunk, self.output_identity)
    }
    // Only a non-newline-terminated prefix of a record we could have written
    // can be a torn append. A complete record requires its newline commit marker.
    fn valid_torn_tail(tail: &str, count: usize) -> bool {
        let (index, status) = match tail.split_once(' ') {
            Some((index, status)) => (index, Some(status)),
            None => (tail, None),
        };
        if index.is_empty() || !index.bytes().all(|c| c.is_ascii_digit()) ||
            (index.len() > 1 && index.starts_with('0')) {
            return false;
        }
        if !matches!(index.parse::<usize>(), Ok(i) if i < count) {
            return false;
        }
        matches!(status, None | Some("") | Some("1") | Some("2"))
    }

    fn parse(contents: &str, expected: &Self) -> io::Result<(Self, u64)> {
        let header = expected.header();
        if !contents.starts_with(&header) {
            return Err(io::Error::new(io::ErrorKind::InvalidData, "rescue map identity mismatch, incomplete header, or legacy unbound map; start a new rescue"));
        }
        let rows = &contents[header.len()..];
        let complete_len = rows.rfind('\n').map_or(0, |i| i + 1);
        let tail = &rows[complete_len..];
        if !tail.is_empty() && !Self::valid_torn_tail(tail, expected.chunks.len()) {
            return Err(io::Error::new(io::ErrorKind::InvalidData, "malformed rescue map trailing update"));
        }
        let mut state = expected.clone();
        for line in rows[..complete_len].lines() {
            let mut fields = line.split_whitespace();
            let index: usize = fields.next().ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "map row empty"))?
                .parse().map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "invalid map index"))?;
            let value: u8 = fields.next().ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "map value absent"))?
                .parse().map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "invalid map value"))?;
            if fields.next().is_some() || index >= state.chunks.len() || !(1..=2).contains(&value) {
                return Err(io::Error::new(io::ErrorKind::InvalidData, "malformed rescue map update"));
            }
            state.chunks[index] = value;
        }
        Ok((state, (header.len() + complete_len) as u64))
    }

    pub fn load(path: &Path, expected: &Self) -> io::Result<Self> {
        Ok(Self::parse(&fs::read_to_string(path)?, expected)?.0)
    }

}

#[derive(Default, Debug)]
pub struct RescueReport {
    pub chunks_total: usize,
    pub chunks_good: usize,
    pub chunks_missing: usize,
    pub bytes_without_full_read: u64,
}

#[cfg(unix)]
fn same_file(a: &Path, b: &Path) -> io::Result<bool> {
    use std::os::unix::fs::MetadataExt;
    let a = fs::metadata(a)?;
    let b = fs::metadata(b)?;
    Ok(a.dev() == b.dev() && a.ino() == b.ino())
}

#[cfg(not(unix))]
fn same_file(a: &Path, b: &Path) -> io::Result<bool> {
    // The current beta only supports NEW outputs on Windows; resume is
    // disabled there to avoid a hard-link alias overwriting the source.
    Ok(fs::canonicalize(a)? == fs::canonicalize(b)?)
}

#[cfg(unix)]
fn output_identity(file: &File) -> io::Result<String> {
    use std::os::unix::fs::MetadataExt;
    let st = file.metadata()?;
    if !st.is_file() || st.ino() == 0 {
        return Err(io::Error::new(io::ErrorKind::InvalidData, "destination has no usable regular file identity"));
    }
    Ok(format!("{}:{}", st.dev(), st.ino()))
}

#[cfg(not(unix))]
fn output_identity(_file: &File) -> io::Result<String> {
    Ok("resume-unsupported".to_string())
}

pub struct RescueOptions<'a> {
    pub input: &'a Path,
    pub output: &'a Path,
    pub map_path: &'a Path,
    pub chunk: usize,
    pub resume: bool,
    pub second_pass: bool,
}

/// Safe image-only multipass copier. The input is opened READ-ONLY; the output
/// is a new regular file (or a previously journaled output on resume).
/// Map updates are durable only AFTER destination fsync. A crash may force a
/// harmless reread, but never marks uncommitted output as fully recovered.
pub fn rescue_image(opts: &RescueOptions<'_>) -> io::Result<RescueReport> {
    let (source, size, stamp) = image_identity(opts.input)?;
    #[cfg(not(unix))]
    if opts.resume {
        return Err(io::Error::new(io::ErrorKind::Unsupported,
            "Rust-core resume requires a supported file identity on this platform."));
    }
    if opts.input == opts.output || opts.input == opts.map_path || opts.output == opts.map_path {
        return Err(io::Error::new(io::ErrorKind::InvalidInput, "image, destination and map paths must differ"));
    }
    // Reject destination aliases or symlinks, even when apparent paths differ.
    for path in [opts.output, opts.map_path] {
        if let Ok(canon) = fs::canonicalize(path) {
            if canon == fs::canonicalize(opts.input)? || same_file(opts.input, path)? {
                return Err(io::Error::new(io::ErrorKind::InvalidInput, "destination aliases patient"));
            }
        }
    }
    let sector = if size % 512 == 0 { 512 } else { 1 };
    let mut expected = Map::new(source, size, stamp, opts.chunk)?;
    let mut state;
    let mut output;
    let mut journal;
    if opts.resume {
        image_identity(opts.output).and_then(|(_, n, _)| if n == size { Ok(()) } else {
            Err(io::Error::new(io::ErrorKind::InvalidData, "destination image size changed"))
        })?;
        output = OpenOptions::new().read(true).write(true).open(opts.output)?;
        expected.output_identity = output_identity(&output)?;
        journal = OpenOptions::new().read(true).append(true).open(opts.map_path)?;
        let mut contents = String::new();
        journal.read_to_string(&mut contents)?;
        let (loaded, valid_len) = Map::parse(&contents, &expected)?;
        state = loaded;
        if valid_len < contents.len() as u64 {
            // Remove a torn suffix before appending, and make the repair durable.
            journal.set_len(valid_len)?;
            journal.sync_all()?;
        }
    } else {
        if opts.map_path.exists() || opts.output.exists() {
            return Err(io::Error::new(io::ErrorKind::AlreadyExists, "new output and map paths required"));
        }
        output = OpenOptions::new().read(true).write(true).create_new(true).open(opts.output)?;
        output.set_len(size)?;
        output.sync_all()?;
        journal = OpenOptions::new().write(true).create_new(true).open(opts.map_path)?;
        expected.output_identity = output_identity(&output)?;
        state = expected;
        journal.write_all(state.header().as_bytes())?;
        journal.sync_all()?;
    }
    let mut input = File::open(opts.input)?;
    let mut buffer = Vec::new();
    let mut pending: Vec<(usize, u8)> = Vec::new();
    let total = state.chunks.len();
    let check = |index: usize, split: bool, st: &mut Map, src: &mut File, dst: &mut File,
                 journal: &mut File, pending: &mut Vec<(usize, u8)>,
                 scratch: &mut Vec<u8>| -> io::Result<()> {
        if st.chunks[index] == 1 {
            return Ok(());
        }
        let offset = index as u64 * opts.chunk as u64;
        let n = usize::try_from((size - offset).min(opts.chunk as u64)).map_err(|_| io::Error::other("length overflow"))?;
        let result = copy_region(src, dst, offset, n, sector, split, scratch)?;
        let status = if result { 1 } else { 2 };
        pending.push((index, status));
        // Flush blocks in bounded batches. Crash before map update causes
        // reread, not false recovery claims. No source writes, ever.
        if pending.len() >= 64 {
            dst.sync_data()?;
            for (i, v) in pending.drain(..) {
                writeln!(journal, "{} {}", i, v)?;
                st.chunks[i] = v;
            }
            journal.sync_all()?;
        }
        Ok(())
    };
    for i in 0..total {
        if state.chunks[i] == 0 {
            check(i, false, &mut state, &mut input, &mut output, &mut journal, &mut pending, &mut buffer)?;
        }
    }
    if !pending.is_empty() {
        output.sync_data()?;
        for (i, v) in pending.drain(..) {
            writeln!(journal, "{} {}", i, v)?;
            state.chunks[i] = v;
        }
        journal.sync_all()?;
    }
    if opts.second_pass {
        // Reverse order on the second pass, splitting only failed regions.
        for i in (0..total).rev() {
            if state.chunks[i] == 2 {
                check(i, true, &mut state, &mut input, &mut output, &mut journal, &mut pending, &mut buffer)?;
            }
        }
        if !pending.is_empty() {
            output.sync_data()?;
            for (i, v) in pending.drain(..) {
                writeln!(journal, "{} {}", i, v)?;
                state.chunks[i] = v;
            }
            journal.sync_all()?;
        }
    }
    // A file being actively modified is not a reliable forensic image.
    let (final_source, final_size, final_stamp) = image_identity(opts.input)?;
    if final_source != state.source || final_size != size || final_stamp != stamp {
        return Err(io::Error::new(io::ErrorKind::InvalidData,
            "patient image changed during rescue; output must not be certified"));
    }
    Ok(RescueReport {
        chunks_total: total,
        chunks_good: state.chunks.iter().filter(|&&v| v == 1).count(),
        chunks_missing: state.chunks.iter().filter(|&&v| v != 1).count(),
        bytes_without_full_read: state.chunks.iter().enumerate().filter(|(_, &v)| v != 1).map(|(i, _)| {
            (size - i as u64 * opts.chunk as u64).min(opts.chunk as u64)
        }).sum(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    struct Injected { bytes: Vec<u8>, bad: std::ops::Range<usize> }
    struct Sink { output: Vec<u8> }
    impl ReadAt for Injected {
        fn read_at(&mut self, offset: u64, output: &mut [u8]) -> io::Result<()> {
            let start = offset as usize;
            if start < self.bad.end && start + output.len() > self.bad.start {
                return Err(io::Error::new(io::ErrorKind::Other, "injected fault"));
            }
            output.copy_from_slice(&self.bytes[start..start + output.len()]);
            Ok(())
        }
    }
    impl WriteAt for Sink {
        fn write_at(&mut self, offset: u64, data: &[u8]) -> io::Result<()> {
            self.output[offset as usize..offset as usize + data.len()].copy_from_slice(data);
            Ok(())
        }
    }
    #[test]
    fn split_read_salvages_valid_sectors_without_certifying_failed_region() {
        let mut source = Injected { bytes: vec![0x47; 4096], bad: 1024..1536 };
        let mut output = Sink { output: vec![0; 4096] };
        let mut scratch = Vec::new();
        assert!(!copy_region(&mut source, &mut output, 0, 4096, 512, true, &mut scratch).unwrap());
        assert_eq!(&output.output[0..1024], &vec![0x47; 1024]);
        assert_eq!(&output.output[1024..1536], &vec![0; 512]);
        assert_eq!(&output.output[1536..4096], &vec![0x47; 2560]);
    }
    #[test]
    fn identity_rejects_invalid_chunks() {
        assert!(Map::new("x".into(), 4096, 0, 513).is_err());
        assert_eq!(Map::new("x".into(), 4096, 0, 512).unwrap().chunks.len(), 8);
    }
    #[test]
    fn map_roundtrip_rejects_foreign_identity() {
        let a = Map::new("source_a".into(), 4096, 1, 512).unwrap();
        let b = Map::new("source_b".into(), 4096, 1, 512).unwrap();
        assert_ne!(a.header(), b.header());
    }
    #[test]
    fn map_torn_tail_boundaries_and_invalid_records() {
        let mut expected = Map::new("source".into(), 1024, 1, 512).unwrap();
        expected.output_identity = "device:inode".into();
        let header = expected.header();
        // Every byte boundary of a record: only the newline commits it.
        for cut in 0..=4 {
            let text = format!("{}0 1\n{}", header, &"1 1\n"[..cut]);
            let (state, end) = Map::parse(&text, &expected).unwrap();
            assert_eq!(state.chunks, if cut == 4 { vec![1, 1] } else { vec![1, 0] });
            assert_eq!(end as usize, header.len() + 4 + if cut == 4 { 4 } else { 0 });
        }
        for cut in 0..header.len() {
            assert!(Map::parse(&header[..cut], &expected).is_err(), "header cut {cut}");
        }
        for bad in ["x", "0 3", "2", "01", "0 1x", "0 1\ninvalid\n", "0 3\n"] {
            assert!(Map::parse(&format!("{header}{bad}"), &expected).is_err(), "bad record {bad:?}");
        }
    }

    #[cfg(unix)]
    #[test]
    fn interrupted_rescue_truncates_torn_tail_before_appending() {
        use std::time::{SystemTime, UNIX_EPOCH};
        let dir = std::env::temp_dir().join(format!("driverepair_torn_{}_{}", std::process::id(), SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos()));
        fs::create_dir(&dir).unwrap();
        let source = dir.join("source");
        let dest = dir.join("dest");
        let map = dir.join("map");
        let data = vec![0xAC; 1536];
        fs::write(&source, &data).unwrap();
        // Generate a bound journal, then simulate a crash after first chunk
        // committed and the next append began. Output already contains data,
        // as required by the data-before-journal protocol.
        let opts = RescueOptions { input: &source, output: &dest, map_path: &map, chunk: 512, resume: false, second_pass: false };
        rescue_image(&opts).unwrap();
        let text = fs::read_to_string(&map).unwrap();
        let header: String = text.lines().take(6).map(|l| format!("{l}\n")).collect();
        fs::write(&map, format!("{header}0 1\n1 ")).unwrap();
        let resumed = RescueOptions { resume: true, ..opts };
        let report = rescue_image(&resumed).unwrap();
        assert_eq!(report.chunks_good, 3);
        assert_eq!(fs::read(&dest).unwrap(), data);
        assert_eq!(fs::read_to_string(&map).unwrap(), format!("{header}0 1\n1 1\n2 1\n"));
        assert_eq!(rescue_image(&resumed).unwrap().chunks_good, 3);
        fs::remove_dir_all(dir).unwrap();
    }

    #[cfg(unix)]
    #[test]
    fn replaced_output_and_legacy_map_are_rejected() {
        use std::time::{SystemTime, UNIX_EPOCH};
        let dir = std::env::temp_dir().join(format!("driverepair_identity_{}_{}", std::process::id(), SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos()));
        fs::create_dir(&dir).unwrap();
        let source = dir.join("source");
        let dest = dir.join("dest");
        let map = dir.join("map");
        fs::write(&source, vec![7; 1024]).unwrap();
        let opts = RescueOptions { input: &source, output: &dest, map_path: &map, chunk: 512, resume: false, second_pass: false };
        rescue_image(&opts).unwrap();
        let saved = fs::read(&map).unwrap();
        let v2 = String::from_utf8(saved.clone()).unwrap();
        let mut fields: Vec<_> = v2.lines().collect();
        fields[0] = "DRIVEREPAIR_IMAGE_MAP_V1";
        fields.remove(5); // V1 did not contain output identity
        let old = fields.join("\n") + "\n";
        fs::write(&map, &old).unwrap();
        let resumed = RescueOptions { resume: true, ..opts };
        assert!(rescue_image(&resumed).is_err());
        assert_eq!(fs::read_to_string(&map).unwrap(), old);
        fs::write(&map, &saved).unwrap();
        let replacement = dir.join("replacement");
        fs::write(&replacement, vec![9; 1024]).unwrap();
        fs::rename(&replacement, &dest).unwrap();
        assert!(rescue_image(&resumed).is_err());
        assert_eq!(fs::read(&map).unwrap(), saved);
        assert_eq!(fs::read(&dest).unwrap(), vec![9; 1024]);
        fs::remove_dir_all(dir).unwrap();
    }
    #[test]
    fn image_rescue_roundtrip_and_new_destination_requirement() {
        use std::time::{SystemTime, UNIX_EPOCH};
        let unique = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
        let dir = std::env::temp_dir().join(format!("driverepair_core_{}_{}", std::process::id(), unique));
        fs::create_dir(&dir).unwrap();
        let source = dir.join("source.img");
        let destination = dir.join("result.img");
        let map = dir.join("result.rmap");
        let expected = vec![0xAC; 1536];
        fs::write(&source, &expected).unwrap();
        let opts = RescueOptions { input: &source, output: &destination,
                                   map_path: &map, chunk: 512, resume: false, second_pass: true };
        let report = rescue_image(&opts).unwrap();
        assert_eq!(report.chunks_missing, 0);
        assert_eq!(fs::read(&destination).unwrap(), expected);
        assert!(rescue_image(&opts).is_err()); // Never silently overwrite.
        #[cfg(unix)] {
            let resumed = RescueOptions { resume: true, ..opts };
            assert_eq!(rescue_image(&resumed).unwrap().chunks_good, 3);
        }
        fs::remove_dir_all(&dir).unwrap();
    }

}
