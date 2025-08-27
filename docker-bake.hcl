group "default" {
    targets = ["visualisation", "parser"]
}

target "visualisation" {
    context = "."
    dockerfile = "Dockerfile.nginx"
    platforms = ["linux/amd64", "linux/arm64"]
    tags = ["qualifier:5000/cubesatsim-aprs-parser-visualisation:main"]
    output = [ "type=registry" ]
}

target "parser" {
    context = "."
    dockerfile = "Dockerfile"
    platforms = ["linux/amd64", "linux/arm64"]
    tags = ["qualifier:5000/cubesatsim-aprs-parser-parser:main"]
    output = [ "type=registry" ]
}
