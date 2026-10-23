fn main() {
    for filename in std::env::args().skip(1) {
        let contents = std::fs::read(&filename).unwrap();
        println!("{} {}", blake3::hash(&contents), filename);
    }
}
