use driverepair_recovery_core::{rescue_image, RescueOptions, DEFAULT_CHUNK};
use std::path::Path;

fn run() -> Result<i32, Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 4 || args[1] != "rescue-image" {
        eprintln!("Usage: driverepair-recovery-core rescue-image SOURCE_IMAGE NEW_OUTPUT_IMAGE [--resume] [--no-second-pass] [--chunk-mib N]");
        return Ok(64);
    }
    let mut resume = false;
    let mut second_pass = true;
    let mut chunk = DEFAULT_CHUNK;
    let mut i = 4;
    while i < args.len() {
        match args[i].as_str() {
            "--resume" => resume = true,
            "--no-second-pass" => second_pass = false,
            "--chunk-mib" => {
                i += 1;
                let m: usize = args.get(i).ok_or("missing MiB count")?.parse()?;
                if m == 0 || m > 64 { return Err("chunk size must be 1-64 MiB".into()); }
                chunk = m * 1024 * 1024;
            }
            _ => return Err(format!("unknown argument: {}", args[i]).into()),
        }
        i += 1;
    }
    let output = Path::new(&args[3]);
    let map = format!("{}.rmap", output.display());
    let result = rescue_image(&RescueOptions {
        input: Path::new(&args[2]), output, map_path: Path::new(&map),
        resume, second_pass, chunk,
    })?;
    println!("{{\"operation\":\"rust_rescue_image\",\"status\":\"{}\",\"chunks_total\":{},\"chunks_good\":{},\"chunks_missing\":{},\"bytes_without_full_read\":{},\"map_path\":\"saved_alongside_output\"}}",
             if result.chunks_missing == 0 { "completed" } else { "incomplete_with_missing_regions" },
             result.chunks_total, result.chunks_good, result.chunks_missing,
             result.bytes_without_full_read);
    Ok(if result.chunks_missing == 0 { 0 } else { 2 })
}

fn main() {
    let result = std::panic::catch_unwind(run);
    let code = match result {
        Ok(Ok(code)) => code,
        Ok(Err(err)) => { eprintln!("DriveRepair Rust core error: {err}"); 1 }
        Err(_) => { eprintln!("DriveRepair Rust core aborted after panic"); 1 }
    };
    std::process::exit(code);
}
