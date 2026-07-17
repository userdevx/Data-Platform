INTELLIGENCE_EXECUTION_MANIFEST = {
    "system.read_cpu": {
        "enabled": True,
        "risk": "low",
        "requires_network": False,
        "requires_credentials": False,
        "requires_filesystem": False,
        "allowed_params": {},
    },
    "system.read_memory": {
        "enabled": True,
        "risk": "low",
        "requires_network": False,
        "requires_credentials": False,
        "requires_filesystem": False,
        "allowed_params": {},
    },
    "system.read_disk": {
        "enabled": True,
        "risk": "low",
        "requires_network": False,
        "requires_credentials": False,
        "requires_filesystem": True,
        "allowed_params": {},
    },
    "system.read_uptime": {
        "enabled": True,
        "risk": "low",
        "requires_network": False,
        "requires_credentials": False,
        "requires_filesystem": False,
        "allowed_params": {},
    },
    "files.read_approved": {
        "enabled": True,
        "risk": "medium",
        "requires_network": False,
        "requires_credentials": False,
        "requires_filesystem": True,
        "allowed_paths": [
            "data/knowledge/pages/*",
            "data/user_uploads/*",
            "data/approved_sources/*",
        ],
        "forbidden_paths": [
            "/etc/passwd",
            "/etc/shadow",
            "/root/*",
            "/home/*/.ssh/*",
            "/proc/*/environ",
            "/proc/self/environ",
            ".env",
            "**/.env",
        ],
        "max_file_size_mb": 25,
        "allowed_params": {
            "path": {
                "type": "string",
                "required": True,
                "max_length": 300,
                "pattern": "safe_path",
            },
        },
    },
    "internet.search_web": {
        "enabled": True,
        "risk": "medium",
        "requires_network": True,
        "requires_credentials": False,
        "requires_filesystem": False,
        "allowed_domains": [
            "html.duckduckgo.com",
            "duckduckgo.com",
        ],
        "forbidden_domains": [
            "169.254.169.254",
            "metadata.google.internal",
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
        ],
        "allowed_params": {
            "query": {
                "type": "string",
                "required": True,
                "max_length": 300,
            },
            "limit": {
                "type": "integer",
                "required": False,
                "minimum": 1,
                "maximum": 10,
            },
        },
    },
    "network.call_approved_api": {
        "enabled": False,
        "risk": "medium",
        "requires_network": True,
        "requires_credentials": True,
        "requires_filesystem": False,
        "allowed_domains": [
            "api.openai.com",
        ],
        "forbidden_domains": [
            "169.254.169.254",
            "metadata.google.internal",
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
        ],
        "allowed_params": {
            "domain": {
                "type": "string",
                "required": True,
                "max_length": 200,
            },
            "endpoint": {
                "type": "string",
                "required": True,
                "max_length": 300,
                "pattern": "api_endpoint",
            },
            "method": {
                "type": "string",
                "required": True,
                "enum": ["GET", "POST"],
            },
        },
    },
    "shell.run": {
        "enabled": False,
        "risk": "critical",
        "requires_network": False,
        "requires_credentials": False,
        "requires_filesystem": True,
        "allowed_params": {
            "command": {
                "type": "string",
                "required": True,
            },
        },
    },
    "filesystem.write": {
        "enabled": False,
        "risk": "critical",
        "requires_network": False,
        "requires_credentials": False,
        "requires_filesystem": True,
        "allowed_params": {
            "path": {
                "type": "string",
                "required": True,
            },
            "content": {
                "type": "string",
                "required": True,
            },
        },
    },
    "internet.read_page": {
        "enabled": True,
        "risk": "medium",
        "requires_network": True,
        "requires_credentials": False,
        "requires_filesystem": True,
        "allowed_params": {
            "url": {
                "type": "string",
                "required": True,
                "max_length": 2000
            },
            "title": {
                "type": "string",
                "required": False,
                "max_length": 300
            }
        },
    },

}
