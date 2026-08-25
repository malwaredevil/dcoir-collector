# Generated DCOIR Knowledge Projection

> Generated, non-canonical output. Edit the atomic files under knowledge/, then rebuild all affected targets.

- Target: openai_dcoir_analyst
- Projection group: dcoir_elastic_reference
- Purpose: Elastic field and response-action reference.
- Source count: 2

<!-- DCOIR_SOURCE_BEGIN {"bytes":62843,"git_blob_sha":"3efc596d1656253135b409018a7973e845bc30df","id":"knowledge.reference.elastic_fields","path":"knowledge/Knowledge - Reference - Elastic Field Name Reference.md","sha256":"423c6ad263ec597e7f0c13e78b74626ca4efe443a16d410e5aa00ab416248c32"} -->
# Knowledge - Reference - Elastic Field Name Reference

_Exact Elastic field-name reference for governed Gemini query construction_

**Summary:** Use this attachment when exact known Elastic field names are needed for KQL or ESQL construction. Preserve field names exactly as written here.

---

## Field names

```text
@timestamp
@version
Acknowledged
Acknowledged.keyword
Division
Effective_process
Effective_process.code_signature
Effective_process.code_signature.exists
Effective_process.code_signature.signing_id
Effective_process.code_signature.status
Effective_process.code_signature.subject_name
Effective_process.code_signature.team_id
Effective_process.code_signature.trusted
Effective_process.entity_id
Effective_process.executable
Effective_process.name
Effective_process.pid
EmailAddress
Endpoint
Endpoint.policy
Endpoint.policy.applied
Endpoint.policy.applied.artifacts
Endpoint.policy.applied.artifacts.global
Endpoint.policy.applied.artifacts.global.channel
Endpoint.policy.applied.artifacts.global.identifiers
Endpoint.policy.applied.artifacts.global.identifiers.name
Endpoint.policy.applied.artifacts.global.identifiers.sha256
Endpoint.policy.applied.artifacts.global.manifest_type
Endpoint.policy.applied.artifacts.global.snapshot
Endpoint.policy.applied.artifacts.global.update_age
Endpoint.policy.applied.artifacts.global.version
Endpoint.policy.applied.artifacts.user
Endpoint.policy.applied.artifacts.user.identifiers
Endpoint.policy.applied.artifacts.user.identifiers.name
Endpoint.policy.applied.artifacts.user.identifiers.sha256
Endpoint.policy.applied.artifacts.user.version
Endpoint.policy.applied.id
Endpoint.policy.applied.name
Endpoint.policy.applied.status
Endpoint.policy.applied.version
LastLogonDate
Memory_protection
Memory_protection.cross_session
Memory_protection.feature
Memory_protection.parent_to_child
Memory_protection.self_injection
Memory_protection.thread_count
Memory_protection.unique_key_v1
Memory_protection.unique_key_v2
Organization
Persistence
Persistence.args
Persistence.executable
Persistence.keepalive
Persistence.name
Persistence.path
Persistence.runatload
Ransomware
Ransomware.child_processes
Ransomware.child_processes.executable
Ransomware.child_processes.executable.text
Ransomware.child_processes.feature
Ransomware.child_processes.files
Ransomware.child_processes.files.data
Ransomware.child_processes.files.entropy
Ransomware.child_processes.files.extension
Ransomware.child_processes.files.metrics
Ransomware.child_processes.files.operation
Ransomware.child_processes.files.original
Ransomware.child_processes.files.original.extension
Ransomware.child_processes.files.original.path
Ransomware.child_processes.files.path
Ransomware.child_processes.files.score
Ransomware.child_processes.pid
Ransomware.child_processes.score
Ransomware.child_processes.version
Ransomware.executable
Ransomware.executable.text
Ransomware.feature
Ransomware.files
Ransomware.files.data
Ransomware.files.entropy
Ransomware.files.extension
Ransomware.files.metrics
Ransomware.files.operation
Ransomware.files.original
Ransomware.files.original.extension
Ransomware.files.original.path
Ransomware.files.path
Ransomware.files.score
Ransomware.pid
Ransomware.score
Ransomware.version
Responses
Responses.@timestamp
Responses.action
Responses.action.action
Responses.action.field
Responses.action.file
Responses.action.file.attributes
Responses.action.file.path
Responses.action.file.reason
Responses.action.key
Responses.action.key.actions
Responses.action.key.path
Responses.action.key.values
Responses.action.key.values.actions
Responses.action.key.values.name
Responses.action.process
Responses.action.process.message
Responses.action.process.path
Responses.action.process.result
Responses.action.source
Responses.action.source.attributes
Responses.action.source.path
Responses.action.state
Responses.action.tree
Responses.message
Responses.process
Responses.process.entity_id
Responses.process.name
Responses.process.pid
Responses.result
Target
Target.dll
Target.dll.Ext
Target.dll.Ext.code_signature
Target.dll.Ext.code_signature.exists
Target.dll.Ext.code_signature.status
Target.dll.Ext.code_signature.subject_name
Target.dll.Ext.code_signature.trusted
Target.dll.Ext.code_signature.valid
Target.dll.Ext.compile_time
Target.dll.Ext.malware_classification
Target.dll.Ext.malware_classification.features
Target.dll.Ext.malware_classification.features.data
Target.dll.Ext.malware_classification.features.data.buffer
Target.dll.Ext.malware_classification.features.data.decompressed_size
Target.dll.Ext.malware_classification.features.data.encoding
Target.dll.Ext.malware_classification.identifier
Target.dll.Ext.malware_classification.score
Target.dll.Ext.malware_classification.threshold
Target.dll.Ext.malware_classification.upx_packed
Target.dll.Ext.malware_classification.version
Target.dll.Ext.mapped_address
Target.dll.Ext.mapped_size
Target.dll.code_signature
Target.dll.code_signature.exists
Target.dll.code_signature.signing_id
Target.dll.code_signature.status
Target.dll.code_signature.subject_name
Target.dll.code_signature.team_id
Target.dll.code_signature.trusted
Target.dll.code_signature.valid
Target.dll.hash
Target.dll.hash.md5
Target.dll.hash.sha1
Target.dll.hash.sha256
Target.dll.hash.sha512
Target.dll.name
Target.dll.path
Target.dll.pe
Target.dll.pe.company
Target.dll.pe.description
Target.dll.pe.file_version
Target.dll.pe.imphash
Target.dll.pe.original_file_name
Target.dll.pe.product
Target.process
Target.process.Ext
Target.process.Ext.ancestry
Target.process.Ext.architecture
Target.process.Ext.authentication_id
Target.process.Ext.code_signature
Target.process.Ext.code_signature.exists
Target.process.Ext.code_signature.status
Target.process.Ext.code_signature.subject_name
Target.process.Ext.code_signature.thumbprint_sha256
Target.process.Ext.code_signature.trusted
Target.process.Ext.code_signature.valid
Target.process.Ext.created_suspended
Target.process.Ext.desktop_name
Target.process.Ext.dll
Target.process.Ext.dll.Ext
Target.process.Ext.dll.Ext.code_signature
Target.process.Ext.dll.Ext.code_signature.exists
Target.process.Ext.dll.Ext.code_signature.status
Target.process.Ext.dll.Ext.code_signature.subject_name
Target.process.Ext.dll.Ext.code_signature.thumbprint_sha256
Target.process.Ext.dll.Ext.code_signature.trusted
Target.process.Ext.dll.Ext.code_signature.valid
Target.process.Ext.dll.Ext.compile_time
Target.process.Ext.dll.Ext.mapped_address
Target.process.Ext.dll.Ext.mapped_size
Target.process.Ext.dll.code_signature
Target.process.Ext.dll.code_signature.exists
Target.process.Ext.dll.code_signature.signing_id
Target.process.Ext.dll.code_signature.status
Target.process.Ext.dll.code_signature.subject_name
Target.process.Ext.dll.code_signature.team_id
Target.process.Ext.dll.code_signature.thumbprint_sha256
Target.process.Ext.dll.code_signature.trusted
Target.process.Ext.dll.code_signature.valid
Target.process.Ext.dll.hash
Target.process.Ext.dll.hash.md5
Target.process.Ext.dll.hash.sha1
Target.process.Ext.dll.hash.sha256
Target.process.Ext.dll.hash.sha512
Target.process.Ext.dll.name
Target.process.Ext.dll.path
Target.process.Ext.dll.pe
Target.process.Ext.dll.pe.company
Target.process.Ext.dll.pe.description
Target.process.Ext.dll.pe.file_version
Target.process.Ext.dll.pe.imphash
Target.process.Ext.dll.pe.original_file_name
Target.process.Ext.dll.pe.product
Target.process.Ext.malware_classification
Target.process.Ext.malware_classification.features
Target.process.Ext.malware_classification.features.data
Target.process.Ext.malware_classification.features.data.buffer
Target.process.Ext.malware_classification.features.data.decompressed_size
Target.process.Ext.malware_classification.features.data.encoding
Target.process.Ext.malware_classification.identifier
Target.process.Ext.malware_classification.score
Target.process.Ext.malware_classification.threshold
Target.process.Ext.malware_classification.upx_packed
Target.process.Ext.malware_classification.version
Target.process.Ext.memory_region
Target.process.Ext.memory_region.allocation_base
Target.process.Ext.memory_region.allocation_protection
Target.process.Ext.memory_region.allocation_size
Target.process.Ext.memory_region.allocation_type
Target.process.Ext.memory_region.bytes_address
Target.process.Ext.memory_region.bytes_allocation_offset
Target.process.Ext.memory_region.bytes_compressed
Target.process.Ext.memory_region.bytes_compressed_present
Target.process.Ext.memory_region.hash
Target.process.Ext.memory_region.hash.sha256
Target.process.Ext.memory_region.malware_signature
Target.process.Ext.memory_region.malware_signature.all_names
Target.process.Ext.memory_region.malware_signature.identifier
Target.process.Ext.memory_region.malware_signature.primary
Target.process.Ext.memory_region.malware_signature.primary.matches
Target.process.Ext.memory_region.malware_signature.primary.signature
Target.process.Ext.memory_region.malware_signature.primary.signature.hash
Target.process.Ext.memory_region.malware_signature.primary.signature.hash.sha256
Target.process.Ext.memory_region.malware_signature.primary.signature.id
Target.process.Ext.memory_region.malware_signature.primary.signature.name
Target.process.Ext.memory_region.malware_signature.secondary
Target.process.Ext.memory_region.malware_signature.secondary.matches
Target.process.Ext.memory_region.malware_signature.secondary.signature
Target.process.Ext.memory_region.malware_signature.secondary.signature.hash
Target.process.Ext.memory_region.malware_signature.secondary.signature.hash.sha256
Target.process.Ext.memory_region.malware_signature.secondary.signature.id
Target.process.Ext.memory_region.malware_signature.secondary.signature.name
Target.process.Ext.memory_region.malware_signature.version
Target.process.Ext.memory_region.mapped_path
Target.process.Ext.memory_region.mapped_pe
Target.process.Ext.memory_region.mapped_pe.Ext
Target.process.Ext.memory_region.mapped_pe.Ext.dotnet
Target.process.Ext.memory_region.mapped_pe.Ext.sections
Target.process.Ext.memory_region.mapped_pe.Ext.sections.hash
Target.process.Ext.memory_region.mapped_pe.Ext.sections.hash.md5
Target.process.Ext.memory_region.mapped_pe.Ext.sections.hash.sha1
Target.process.Ext.memory_region.mapped_pe.Ext.sections.hash.sha256
Target.process.Ext.memory_region.mapped_pe.Ext.sections.hash.sha384
Target.process.Ext.memory_region.mapped_pe.Ext.sections.hash.sha512
Target.process.Ext.memory_region.mapped_pe.Ext.sections.hash.ssdeep
Target.process.Ext.memory_region.mapped_pe.Ext.sections.hash.tlsh
Target.process.Ext.memory_region.mapped_pe.Ext.sections.name
Target.process.Ext.memory_region.mapped_pe.Ext.streams
Target.process.Ext.memory_region.mapped_pe.Ext.streams.hash
Target.process.Ext.memory_region.mapped_pe.Ext.streams.hash.md5
Target.process.Ext.memory_region.mapped_pe.Ext.streams.hash.sha1
Target.process.Ext.memory_region.mapped_pe.Ext.streams.hash.sha256
Target.process.Ext.memory_region.mapped_pe.Ext.streams.hash.sha384
Target.process.Ext.memory_region.mapped_pe.Ext.streams.hash.sha512
Target.process.Ext.memory_region.mapped_pe.Ext.streams.hash.ssdeep
Target.process.Ext.memory_region.mapped_pe.Ext.streams.hash.tlsh
Target.process.Ext.memory_region.mapped_pe.Ext.streams.name
Target.process.Ext.memory_region.mapped_pe.architecture
Target.process.Ext.memory_region.mapped_pe.company
Target.process.Ext.memory_region.mapped_pe.description
Target.process.Ext.memory_region.mapped_pe.file_version
Target.process.Ext.memory_region.mapped_pe.go_import_hash
Target.process.Ext.memory_region.mapped_pe.go_imports
Target.process.Ext.memory_region.mapped_pe.go_imports_names_entropy
Target.process.Ext.memory_region.mapped_pe.go_imports_names_var_entropy
Target.process.Ext.memory_region.mapped_pe.go_stripped
Target.process.Ext.memory_region.mapped_pe.imphash
Target.process.Ext.memory_region.mapped_pe.import_hash
Target.process.Ext.memory_region.mapped_pe.imports
Target.process.Ext.memory_region.mapped_pe.imports_names_entropy
Target.process.Ext.memory_region.mapped_pe.imports_names_var_entropy
Target.process.Ext.memory_region.mapped_pe.original_file_name
Target.process.Ext.memory_region.mapped_pe.pehash
Target.process.Ext.memory_region.mapped_pe.product
Target.process.Ext.memory_region.mapped_pe.sections
Target.process.Ext.memory_region.mapped_pe.sections.entropy
Target.process.Ext.memory_region.mapped_pe.sections.name
Target.process.Ext.memory_region.mapped_pe.sections.physical_size
Target.process.Ext.memory_region.mapped_pe.sections.var_entropy
Target.process.Ext.memory_region.mapped_pe.sections.virtual_size
Target.process.Ext.memory_region.mapped_pe_detected
Target.process.Ext.memory_region.memory_pe
Target.process.Ext.memory_region.memory_pe.Ext
Target.process.Ext.memory_region.memory_pe.Ext.dotnet
Target.process.Ext.memory_region.memory_pe.Ext.sections
Target.process.Ext.memory_region.memory_pe.Ext.sections.hash
Target.process.Ext.memory_region.memory_pe.Ext.sections.hash.md5
Target.process.Ext.memory_region.memory_pe.Ext.sections.hash.sha1
Target.process.Ext.memory_region.memory_pe.Ext.sections.hash.sha256
Target.process.Ext.memory_region.memory_pe.Ext.sections.hash.sha384
Target.process.Ext.memory_region.memory_pe.Ext.sections.hash.sha512
Target.process.Ext.memory_region.memory_pe.Ext.sections.hash.ssdeep
Target.process.Ext.memory_region.memory_pe.Ext.sections.hash.tlsh
Target.process.Ext.memory_region.memory_pe.Ext.sections.name
Target.process.Ext.memory_region.memory_pe.Ext.streams
Target.process.Ext.memory_region.memory_pe.Ext.streams.hash
Target.process.Ext.memory_region.memory_pe.Ext.streams.hash.md5
Target.process.Ext.memory_region.memory_pe.Ext.streams.hash.sha1
Target.process.Ext.memory_region.memory_pe.Ext.streams.hash.sha256
Target.process.Ext.memory_region.memory_pe.Ext.streams.hash.sha384
Target.process.Ext.memory_region.memory_pe.Ext.streams.hash.sha512
Target.process.Ext.memory_region.memory_pe.Ext.streams.hash.ssdeep
Target.process.Ext.memory_region.memory_pe.Ext.streams.hash.tlsh
Target.process.Ext.memory_region.memory_pe.Ext.streams.name
Target.process.Ext.memory_region.memory_pe.architecture
Target.process.Ext.memory_region.memory_pe.company
Target.process.Ext.memory_region.memory_pe.description
Target.process.Ext.memory_region.memory_pe.file_version
Target.process.Ext.memory_region.memory_pe.go_import_hash
Target.process.Ext.memory_region.memory_pe.go_imports
Target.process.Ext.memory_region.memory_pe.go_imports_names_entropy
Target.process.Ext.memory_region.memory_pe.go_imports_names_var_entropy
Target.process.Ext.memory_region.memory_pe.go_stripped
Target.process.Ext.memory_region.memory_pe.imphash
Target.process.Ext.memory_region.memory_pe.import_hash
Target.process.Ext.memory_region.memory_pe.imports
Target.process.Ext.memory_region.memory_pe.imports_names_entropy
Target.process.Ext.memory_region.memory_pe.imports_names_var_entropy
Target.process.Ext.memory_region.memory_pe.original_file_name
Target.process.Ext.memory_region.memory_pe.pehash
Target.process.Ext.memory_region.memory_pe.product
Target.process.Ext.memory_region.memory_pe.sections
Target.process.Ext.memory_region.memory_pe.sections.entropy
Target.process.Ext.memory_region.memory_pe.sections.name
Target.process.Ext.memory_region.memory_pe.sections.physical_size
Target.process.Ext.memory_region.memory_pe.sections.var_entropy
Target.process.Ext.memory_region.memory_pe.sections.virtual_size
Target.process.Ext.memory_region.memory_pe_detected
Target.process.Ext.memory_region.region_base
Target.process.Ext.memory_region.region_protection
Target.process.Ext.memory_region.region_size
Target.process.Ext.memory_region.region_start_bytes
Target.process.Ext.memory_region.region_state
Target.process.Ext.memory_region.strings
Target.process.Ext.protection
Target.process.Ext.services
Target.process.Ext.session
Target.process.Ext.session_info
Target.process.Ext.session_info.authentication_package
Target.process.Ext.session_info.failure_reason
Target.process.Ext.session_info.id
Target.process.Ext.session_info.logon_process_name
Target.process.Ext.session_info.logon_type
Target.process.Ext.token
Target.process.Ext.token.domain
Target.process.Ext.token.elevation
Target.process.Ext.token.elevation_type
Target.process.Ext.token.impersonation_level
Target.process.Ext.token.integrity_level
Target.process.Ext.token.integrity_level_name
Target.process.Ext.token.is_appcontainer
Target.process.Ext.token.privileges
Target.process.Ext.token.privileges.description
Target.process.Ext.token.privileges.enabled
Target.process.Ext.token.privileges.name
Target.process.Ext.token.sid
Target.process.Ext.token.type
Target.process.Ext.token.user
Target.process.Ext.user
Target.process.args
Target.process.args_count
Target.process.code_signature
Target.process.code_signature.exists
Target.process.code_signature.signing_id
Target.process.code_signature.status
Target.process.code_signature.subject_name
Target.process.code_signature.team_id
Target.process.code_signature.thumbprint_sha256
Target.process.code_signature.trusted
Target.process.code_signature.valid
Target.process.command_line
Target.process.command_line.caseless
Target.process.command_line.text
Target.process.entity_id
Target.process.executable
Target.process.executable.caseless
Target.process.executable.text
Target.process.exit_code
Target.process.hash
Target.process.hash.md5
Target.process.hash.sha1
Target.process.hash.sha256
Target.process.hash.sha512
Target.process.name
Target.process.name.caseless
Target.process.name.text
Target.process.parent
Target.process.parent.Ext
Target.process.parent.Ext.architecture
Target.process.parent.Ext.code_signature
Target.process.parent.Ext.code_signature.exists
Target.process.parent.Ext.code_signature.status
Target.process.parent.Ext.code_signature.subject_name
Target.process.parent.Ext.code_signature.thumbprint_sha256
Target.process.parent.Ext.code_signature.trusted
Target.process.parent.Ext.code_signature.valid
Target.process.parent.Ext.dll
Target.process.parent.Ext.dll.Ext
Target.process.parent.Ext.dll.Ext.code_signature
Target.process.parent.Ext.dll.Ext.code_signature.exists
Target.process.parent.Ext.dll.Ext.code_signature.status
Target.process.parent.Ext.dll.Ext.code_signature.subject_name
Target.process.parent.Ext.dll.Ext.code_signature.thumbprint_sha256
Target.process.parent.Ext.dll.Ext.code_signature.trusted
Target.process.parent.Ext.dll.Ext.code_signature.valid
Target.process.parent.Ext.dll.Ext.compile_time
Target.process.parent.Ext.dll.Ext.mapped_address
Target.process.parent.Ext.dll.Ext.mapped_size
Target.process.parent.Ext.dll.code_signature
Target.process.parent.Ext.dll.code_signature.exists
Target.process.parent.Ext.dll.code_signature.signing_id
Target.process.parent.Ext.dll.code_signature.status
Target.process.parent.Ext.dll.code_signature.subject_name
Target.process.parent.Ext.dll.code_signature.team_id
Target.process.parent.Ext.dll.code_signature.thumbprint_sha256
Target.process.parent.Ext.dll.code_signature.trusted
Target.process.parent.Ext.dll.code_signature.valid
Target.process.parent.Ext.dll.hash
Target.process.parent.Ext.dll.hash.md5
Target.process.parent.Ext.dll.hash.sha1
Target.process.parent.Ext.dll.hash.sha256
Target.process.parent.Ext.dll.hash.sha512
Target.process.parent.Ext.dll.name
Target.process.parent.Ext.dll.path
Target.process.parent.Ext.dll.pe
Target.process.parent.Ext.dll.pe.company
Target.process.parent.Ext.dll.pe.description
Target.process.parent.Ext.dll.pe.file_version
Target.process.parent.Ext.dll.pe.imphash
Target.process.parent.Ext.dll.pe.original_file_name
Target.process.parent.Ext.dll.pe.product
Target.process.parent.Ext.protection
Target.process.parent.Ext.real
Target.process.parent.Ext.real.pid
Target.process.parent.Ext.token
Target.process.parent.Ext.token.domain
Target.process.parent.Ext.token.elevation
Target.process.parent.Ext.token.elevation_type
Target.process.parent.Ext.token.impersonation_level
Target.process.parent.Ext.token.integrity_level
Target.process.parent.Ext.token.integrity_level_name
Target.process.parent.Ext.token.is_appcontainer
Target.process.parent.Ext.token.privileges
Target.process.parent.Ext.token.privileges.description
Target.process.parent.Ext.token.privileges.enabled
Target.process.parent.Ext.token.privileges.name
Target.process.parent.Ext.token.sid
Target.process.parent.Ext.token.type
Target.process.parent.Ext.token.user
Target.process.parent.Ext.user
Target.process.parent.args
Target.process.parent.args_count
Target.process.parent.code_signature
Target.process.parent.code_signature.exists
Target.process.parent.code_signature.signing_id
Target.process.parent.code_signature.status
Target.process.parent.code_signature.subject_name
Target.process.parent.code_signature.team_id
Target.process.parent.code_signature.thumbprint_sha256
Target.process.parent.code_signature.trusted
Target.process.parent.code_signature.valid
Target.process.parent.command_line
Target.process.parent.command_line.caseless
Target.process.parent.command_line.text
Target.process.parent.entity_id
Target.process.parent.executable
Target.process.parent.executable.caseless
Target.process.parent.executable.text
Target.process.parent.exit_code
Target.process.parent.hash
Target.process.parent.hash.md5
Target.process.parent.hash.sha1
Target.process.parent.hash.sha256
Target.process.parent.hash.sha512
Target.process.parent.name
Target.process.parent.name.caseless
Target.process.parent.name.text
Target.process.parent.pe
Target.process.parent.pe.company
Target.process.parent.pe.description
Target.process.parent.pe.file_version
Target.process.parent.pe.imphash
Target.process.parent.pe.original_file_name
Target.process.parent.pe.product
Target.process.parent.pgid
Target.process.parent.pid
Target.process.parent.ppid
Target.process.parent.start
Target.process.parent.thread
Target.process.parent.thread.id
Target.process.parent.thread.name
Target.process.parent.title
Target.process.parent.title.text
Target.process.parent.uptime
Target.process.parent.working_directory
Target.process.parent.working_directory.caseless
Target.process.parent.working_directory.text
Target.process.pe
Target.process.pe.company
Target.process.pe.description
Target.process.pe.file_version
Target.process.pe.imphash
Target.process.pe.original_file_name
Target.process.pe.product
Target.process.pgid
Target.process.pid
Target.process.ppid
Target.process.start
Target.process.thread
Target.process.thread.Ext
Target.process.thread.Ext.call_stack
Target.process.thread.Ext.call_stack.instruction_pointer
Target.process.thread.Ext.call_stack.memory_section
Target.process.thread.Ext.call_stack.memory_section.memory_address
Target.process.thread.Ext.call_stack.memory_section.memory_size
Target.process.thread.Ext.call_stack.memory_section.protection
Target.process.thread.Ext.call_stack.module_name
Target.process.thread.Ext.call_stack.module_path
Target.process.thread.Ext.call_stack.rva
Target.process.thread.Ext.call_stack.symbol_info
Target.process.thread.Ext.call_stack_final_user_module
Target.process.thread.Ext.call_stack_final_user_module.code_signature
Target.process.thread.Ext.call_stack_final_user_module.code_signature.exists
Target.process.thread.Ext.call_stack_final_user_module.code_signature.status
Target.process.thread.Ext.call_stack_final_user_module.code_signature.subject_name
Target.process.thread.Ext.call_stack_final_user_module.code_signature.trusted
Target.process.thread.Ext.call_stack_final_user_module.code_signature.valid
Target.process.thread.Ext.call_stack_final_user_module.hash
Target.process.thread.Ext.call_stack_final_user_module.hash.sha256
Target.process.thread.Ext.call_stack_final_user_module.name
Target.process.thread.Ext.call_stack_final_user_module.path
Target.process.thread.Ext.call_stack_summary
Target.process.thread.Ext.hardware_breakpoint_set
Target.process.thread.Ext.original_start_address
Target.process.thread.Ext.original_start_address_allocation_offset
Target.process.thread.Ext.original_start_address_bytes
Target.process.thread.Ext.original_start_address_bytes_disasm
Target.process.thread.Ext.original_start_address_bytes_disasm_hash
Target.process.thread.Ext.original_start_address_module
Target.process.thread.Ext.parameter
Target.process.thread.Ext.parameter_bytes_compressed
Target.process.thread.Ext.parameter_bytes_compressed_present
Target.process.thread.Ext.service
Target.process.thread.Ext.start
Target.process.thread.Ext.start_address
Target.process.thread.Ext.start_address_allocation_offset
Target.process.thread.Ext.start_address_bytes
Target.process.thread.Ext.start_address_bytes_disasm
Target.process.thread.Ext.start_address_bytes_disasm_hash
Target.process.thread.Ext.start_address_module
Target.process.thread.Ext.token
Target.process.thread.Ext.token.domain
Target.process.thread.Ext.token.elevation
Target.process.thread.Ext.token.elevation_type
Target.process.thread.Ext.token.impersonation_level
Target.process.thread.Ext.token.integrity_level
Target.process.thread.Ext.token.integrity_level_name
Target.process.thread.Ext.token.is_appcontainer
Target.process.thread.Ext.token.privileges
Target.process.thread.Ext.token.privileges.description
Target.process.thread.Ext.token.privileges.enabled
Target.process.thread.Ext.token.privileges.name
Target.process.thread.Ext.token.sid
Target.process.thread.Ext.token.type
Target.process.thread.Ext.token.user
Target.process.thread.Ext.uptime
Target.process.thread.id
Target.process.thread.name
Target.process.title
Target.process.title.text
Target.process.uptime
Target.process.working_directory
Target.process.working_directory.caseless
Target.process.working_directory.text
Tcc
Tcc.identity
Tcc.reason
Tcc.right
Tcc.service
Tcc.update_type
_data_stream_timestamp
_doc_count
_feature
_field_names
_id
_ignored
_ignored_source
_index
_index_mode
_inference_fields
_nested_path
_routing
_seq_no
_source
_temp_
_temp_.date_timezone
_temp_.timestamp
_tier
_version
acas_metadata
acas_metadata.host
acas_metadata.host.ip
acas_metadata.host.name
acas_metadata.host.name.text
acas_metadata.repository
acas_metadata.repository.name
acas_metadata.repository.name.text
acquisitionPathway
acquisitionPathwayLifeCycle
acquisitionPathwayLifecycle
action_data
action_data.ecs_mapping
action_data.ecs_mapping.file
action_data.ecs_mapping.file.directory
action_data.ecs_mapping.file.directory.field
action_data.ecs_mapping.file.gid
action_data.ecs_mapping.file.gid.field
action_data.ecs_mapping.file.inode
action_data.ecs_mapping.file.inode.field
action_data.ecs_mapping.file.mode
action_data.ecs_mapping.file.mode.field
action_data.ecs_mapping.file.name
action_data.ecs_mapping.file.name.field
action_data.ecs_mapping.file.size
action_data.ecs_mapping.file.size.field
action_data.ecs_mapping.file.type
action_data.ecs_mapping.file.type.field
action_data.ecs_mapping.file.uid
action_data.ecs_mapping.file.uid.field
action_data.ecs_mapping.user
action_data.ecs_mapping.user.group
action_data.ecs_mapping.user.group.id
action_data.ecs_mapping.user.group.id.field
action_data.ecs_mapping.user.id
action_data.ecs_mapping.user.id.field
action_data.ecs_mapping.user.name
action_data.ecs_mapping.user.name.field
action_data.id
action_data.platform
action_data.query
action_data.saved_query_id
action_data.version
action_id
action_input_type
action_response
action_response.osquery
action_response.osquery.count
ad
ad.BusType
ad.BusType.l
ad.DeviceFileSystemType
ad.DeviceFileSystemType.l
ad.FileSystemAccess
ad.FileSystemAccess.l
ad_metadata
ad_metadata.destination
ad_metadata.destination.host
ad_metadata.destination.host.distinguished_name
ad_metadata.destination.host.ip
ad_metadata.destination.host.location
ad_metadata.destination.host.name
ad_metadata.destination.host.service
ad_metadata.destination.user
ad_metadata.destination.user.distinguished_name
ad_metadata.destination.user.full_name
ad_metadata.destination.user.name
ad_metadata.destination.user.sam_name
ad_metadata.host
ad_metadata.host.distinguished_name
ad_metadata.host.ip
ad_metadata.host.location
ad_metadata.host.name
ad_metadata.host.name.text
ad_metadata.host.service
ad_metadata.source
ad_metadata.source.host
ad_metadata.source.host.distinguished_name
ad_metadata.source.host.ip
ad_metadata.source.host.location
ad_metadata.source.host.name
ad_metadata.source.host.service
ad_metadata.source.user
ad_metadata.source.user.distinguished_name
ad_metadata.source.user.full_name
ad_metadata.source.user.name
ad_metadata.source.user.sam_name
ad_metadata.user
ad_metadata.user.afrl
ad_metadata.user.distinguished_name
ad_metadata.user.full_name
ad_metadata.user.name
ad_metadata.user.name.text
ad_metadata.user.sam_name
agent
agent.build
agent.build.original
agent.ephemeral_id
agent.id
agent.name
agent.name.text
agent.type
agent.version
agent_id
agent_metadata
agent_metadata.available
agent_metadata.destination
agent_metadata.destination.host
agent_metadata.destination.host.hostname
agent_metadata.destination.host.ip
agent_metadata.destination.host.mac
agent_metadata.destination.host.name
agent_metadata.destination.os
agent_metadata.destination.os.full
agent_metadata.destination.os.kernel
agent_metadata.destination.os.name
agent_metadata.host
agent_metadata.host.hostname
agent_metadata.host.ip
agent_metadata.host.mac
agent_metadata.os
agent_metadata.os.full
agent_metadata.os.kernel
agent_metadata.os.name
agent_metadata.source
agent_metadata.source.host
agent_metadata.source.host.hostname
agent_metadata.source.host.ip
agent_metadata.source.host.mac
agent_metadata.source.host.name
agent_metadata.source.os
agent_metadata.source.os.full
agent_metadata.source.os.kernel
agent_metadata.source.os.name
agent_metadata.tags
agentless
apache
apache.access
apache.access.http
apache.access.http.request_headers
apache.access.identity
apache.access.remote_addresses
apache.access.response_time
apache.access.ssl
apache.access.ssl.cipher
apache.access.ssl.protocol
apache.access.tls_handshake
apache.access.tls_handshake.error
apache.error
apache.error.module
auditd
auditd.log
auditd.log.(enforcing
auditd.log.(seqno
auditd.log.ARCH
auditd.log.AUID
auditd.log.EGID
auditd.log.EUID
auditd.log.FSGID
auditd.log.FSUID
auditd.log.GID
auditd.log.ID
auditd.log.NEW_GID
auditd.log.OAUID
auditd.log.OGID
auditd.log.OLD-AUID
auditd.log.OUID
auditd.log.SAUID
auditd.log.SGID
auditd.log.SUID
auditd.log.SYSCALL
auditd.log.UID
auditd.log.a0
auditd.log.a1
auditd.log.a2
auditd.log.a3
auditd.log.action
auditd.log.added
auditd.log.addr
auditd.log.algo
auditd.log.apparmor
auditd.log.audit_backlog_limit
auditd.log.audit_backlog_wait_time
auditd.log.audit_enabled
auditd.log.audit_failure
auditd.log.audit_pid
auditd.log.avc
auditd.log.avc.action
auditd.log.avc.request
auditd.log.bool
auditd.log.cap_fe
auditd.log.cap_fi
auditd.log.cap_fp
auditd.log.cap_frootid
auditd.log.cap_fver
auditd.log.capability
auditd.log.changed
auditd.log.cipher
auditd.log.cmdline
auditd.log.code
auditd.log.compat
auditd.log.context
auditd.log.data
auditd.log.default-context
auditd.log.dest
auditd.log.dev
auditd.log.device
auditd.log.device_rule
auditd.log.direction
auditd.log.dst_prefixlen
auditd.log.enabled
auditd.log.enforcing
auditd.log.entries
auditd.log.family
auditd.log.fan_info
auditd.log.fan_type
auditd.log.fd
auditd.log.fe
auditd.log.feature
auditd.log.fi
auditd.log.flags
auditd.log.format
auditd.log.fp
auditd.log.frootid
auditd.log.ftype
auditd.log.func
auditd.log.function
auditd.log.fver
auditd.log.gpg_res
auditd.log.grantors
auditd.log.grp
auditd.log.hostname
auditd.log.id
auditd.log.img-ctx
auditd.log.info
auditd.log.ino
auditd.log.inode
auditd.log.invalid_context
auditd.log.ioctlcmd
auditd.log.ip
auditd.log.item
auditd.log.items
auditd.log.kernel
auditd.log.key
auditd.log.key_enforce
auditd.log.kind
auditd.log.ksize
auditd.log.laddr
auditd.log.list
auditd.log.lport
auditd.log.lsm
auditd.log.mac
auditd.log.major
auditd.log.minor
auditd.log.mode
auditd.log.model
auditd.log.name
auditd.log.nametype
auditd.log.new
auditd.log.new-context
auditd.log.new-level
auditd.log.new-range
auditd.log.new-role
auditd.log.new-seuser
auditd.log.new_auid
auditd.log.new_gid
auditd.log.new_lock
auditd.log.new_pe
auditd.log.new_pi
auditd.log.new_pp
auditd.log.new_ses
auditd.log.nl-mcgrp
auditd.log.nlbl_domain
auditd.log.nlbl_protocol
auditd.log.nlnk-fam
auditd.log.nlnk-pid
auditd.log.node
auditd.log.oauid
auditd.log.obj
auditd.log.obj_trust
auditd.log.objtype
auditd.log.ocomm
auditd.log.old
auditd.log.old-context
auditd.log.old-enabled
auditd.log.old-level
auditd.log.old-range
auditd.log.old-role
auditd.log.old-seuser
auditd.log.old_auid
auditd.log.old_enforcing
auditd.log.old_lock
auditd.log.old_pa
auditd.log.old_pe
auditd.log.old_pi
auditd.log.old_pp
auditd.log.old_prom
auditd.log.old_ses
auditd.log.old_val
auditd.log.op
auditd.log.operation
auditd.log.opid
auditd.log.original_field
auditd.log.oses
auditd.log.pa
auditd.log.path
auditd.log.pe
auditd.log.permissive
auditd.log.pfs
auditd.log.pi
auditd.log.pp
auditd.log.proctitle
auditd.log.profile
auditd.log.prom
auditd.log.rdev
auditd.log.reason
auditd.log.record_type
auditd.log.removed
auditd.log.request
auditd.log.reset
auditd.log.resp
auditd.log.resrc
auditd.log.root_dir
auditd.log.rport
auditd.log.saddr
auditd.log.saddr_fam
auditd.log.sauid
auditd.log.scontext
auditd.log.selected-context
auditd.log.sequence
auditd.log.ses
auditd.log.sig
auditd.log.size
auditd.log.spid
auditd.log.src_prefixlen
auditd.log.state
auditd.log.subj
auditd.log.subj_trust
auditd.log.success
auditd.log.sw
auditd.log.sw_type
auditd.log.syscall
auditd.log.table
auditd.log.target
auditd.log.tclass
auditd.log.tcontext
auditd.log.tglob
auditd.log.tty
auditd.log.type
auditd.log.uid
auditd.log.unit
auditd.log.unlbl_accept
auditd.log.uuid
auditd.log.val
auditd.log.ver
auditd.log.virt
auditd.log.vm
auditd.log.vm-ctx
auditd.log.xdevice
aws
aws.s3
aws.s3.bucket
aws.s3.bucket.arn
aws.s3.bucket.name
aws.s3.object
aws.s3.object.key
blocklist_label
cisa_kev
cisa_kev.cwes
cisa_kev.vulnerability
cisa_kev.vulnerability.date_added
cisa_kev.vulnerability.due_date
cisa_kev.vulnerability.known_ransomware_campaign_use
cisa_kev.vulnerability.name
cisa_kev.vulnerability.notes
cisa_kev.vulnerability.product
cisa_kev.vulnerability.required_action
cisa_kev.vulnerability.vendor_project
cisco
cisco.ftd
cisco.ftd.aaa_type
cisco.ftd.assigned_ip
cisco.ftd.assigned_ipv6
cisco.ftd.burst
cisco.ftd.burst.avg_rate
cisco.ftd.burst.configured_avg_rate
cisco.ftd.burst.configured_rate
cisco.ftd.burst.cumulative_count
cisco.ftd.burst.current_rate
cisco.ftd.burst.id
cisco.ftd.burst.object
cisco.ftd.command_line_arguments
cisco.ftd.connection_id
cisco.ftd.connection_type
cisco.ftd.dap_records
cisco.ftd.destination_interface
cisco.ftd.destination_user_or_sgt
cisco.ftd.destination_username
cisco.ftd.effective_mtu
cisco.ftd.icmp_code
cisco.ftd.icmp_type
cisco.ftd.mapped_destination_host
cisco.ftd.mapped_destination_ip
cisco.ftd.mapped_destination_port
cisco.ftd.mapped_source_host
cisco.ftd.mapped_source_ip
cisco.ftd.mapped_source_port
cisco.ftd.message
cisco.ftd.message_id
cisco.ftd.missed_updates_count
cisco.ftd.privilege
cisco.ftd.privilege.new
cisco.ftd.privilege.old
cisco.ftd.rule_name
cisco.ftd.security
cisco.ftd.security_event
cisco.ftd.security_event.ac_policy
cisco.ftd.security_event.access_control_rule_action
cisco.ftd.security_event.access_control_rule_name
cisco.ftd.security_event.access_control_rule_reason
cisco.ftd.security_event.application_protocol
cisco.ftd.security_event.client
cisco.ftd.security_event.client_version
cisco.ftd.security_event.connection_duration
cisco.ftd.security_event.destination_ip_dynamic_attribute
cisco.ftd.security_event.destination_security_group
cisco.ftd.security_event.destination_security_group_tag
cisco.ftd.security_event.dns_query
cisco.ftd.security_event.dns_record_type
cisco.ftd.security_event.dns_response_type
cisco.ftd.security_event.dns_ttl
cisco.ftd.security_event.dst_ip
cisco.ftd.security_event.dst_port
cisco.ftd.security_event.egress_interface
cisco.ftd.security_event.egress_zone
cisco.ftd.security_event.encrypt_peer_ip
cisco.ftd.security_event.file_action
cisco.ftd.security_event.file_count
cisco.ftd.security_event.file_direction
cisco.ftd.security_event.file_name
cisco.ftd.security_event.file_policy
cisco.ftd.security_event.file_sandbox_status
cisco.ftd.security_event.file_sha256
cisco.ftd.security_event.file_size
cisco.ftd.security_event.file_type
cisco.ftd.security_event.first_packet_second
cisco.ftd.security_event.http_referer
cisco.ftd.security_event.http_response
cisco.ftd.security_event.icmp_code
cisco.ftd.security_event.icmp_type
cisco.ftd.security_event.ingress_interface
cisco.ftd.security_event.ingress_zone
cisco.ftd.security_event.initiator_bytes
cisco.ftd.security_event.initiator_packets
cisco.ftd.security_event.nap_policy
cisco.ftd.security_event.prefilter_policy
cisco.ftd.security_event.protocol
cisco.ftd.security_event.referenced_host
cisco.ftd.security_event.responder_bytes
cisco.ftd.security_event.responder_packets
cisco.ftd.security_event.sha_disposition
cisco.ftd.security_event.source_security_group
cisco.ftd.security_event.source_security_group_tag
cisco.ftd.security_event.source_security_group_type
cisco.ftd.security_event.spero_disposition
cisco.ftd.security_event.src_ip
cisco.ftd.security_event.src_port
cisco.ftd.security_event.ssl_actual_action
cisco.ftd.security_event.ssl_certificate
cisco.ftd.security_event.ssl_expected_action
cisco.ftd.security_event.ssl_flow_status
cisco.ftd.security_event.ssl_policy
cisco.ftd.security_event.ssl_rule_name
cisco.ftd.security_event.ssl_server_cert_status
cisco.ftd.security_event.ssl_server_name
cisco.ftd.security_event.ssl_session_id
cisco.ftd.security_event.ssl_ticket_id
cisco.ftd.security_event.ssl_version
cisco.ftd.security_event.sslurl_category
cisco.ftd.security_event.tunnel_or_prefilter_rule
cisco.ftd.security_event.uri
cisco.ftd.security_event.url
cisco.ftd.security_event.url_category
cisco.ftd.security_event.url_reputation
cisco.ftd.security_event.user
cisco.ftd.security_event.user_agent
cisco.ftd.security_event.vpn_action
cisco.ftd.security_event.web_application
cisco.ftd.session_type
cisco.ftd.source_interface
cisco.ftd.source_user_or_sgt
cisco.ftd.source_username
cisco.ftd.suffix
cisco.ftd.termination_initiator
cisco.ftd.termination_user
cisco.ftd.threat_category
cisco.ftd.threat_level
cisco.ftd.translation_type
cisco.ftd.tunnel_type
cisco.ftd.username
cisco.ftd.webvpn
cisco.ftd.webvpn.group_name
cisco.ios
cisco.ios.access_list
cisco.ios.action
cisco.ios.facility
cisco.ios.interface
cisco.ios.interface.name
cisco.ios.message_count
cisco.ios.outcome
cisco.ios.pim
cisco.ios.pim.group
cisco.ios.pim.group.ip
cisco.ios.pim.source
cisco.ios.pim.source.ip
cisco.ios.sequence
cisco.ios.session
cisco.ios.session.number
cisco.ios.session.type
cisco.ios.tableid
cisco.ios.uptime
cisco_ise
cisco_ise.log
cisco_ise.log.acct
cisco_ise.log.acct.authentic
cisco_ise.log.acct.delay_time
cisco_ise.log.acct.input
cisco_ise.log.acct.input.octets
cisco_ise.log.acct.input.packets
cisco_ise.log.acct.output
cisco_ise.log.acct.output.octets
cisco_ise.log.acct.output.packets
cisco_ise.log.acct.request
cisco_ise.log.acct.request.flags
cisco_ise.log.acct.session
cisco_ise.log.acct.session.id
cisco_ise.log.acct.session.time
cisco_ise.log.acct.status
cisco_ise.log.acct.status.type
cisco_ise.log.acct.terminate_cause
cisco_ise.log.acme-av-pair
cisco_ise.log.acme-av-pair.audit-session-id
cisco_ise.log.acme-av-pair.service-type
cisco_ise.log.acs
cisco_ise.log.acs.instance
cisco_ise.log.acs.session
cisco_ise.log.acs.session.id
cisco_ise.log.active_session
cisco_ise.log.active_session.count
cisco_ise.log.ad
cisco_ise.log.ad.admin
cisco_ise.log.ad.domain
cisco_ise.log.ad.domain.controller
cisco_ise.log.ad.domain.name
cisco_ise.log.ad.error
cisco_ise.log.ad.error.details
cisco_ise.log.ad.forest
cisco_ise.log.ad.hostname
cisco_ise.log.ad.ip
cisco_ise.log.ad.log
cisco_ise.log.ad.log_id
cisco_ise.log.ad.organization_unit
cisco_ise.log.ad.site
cisco_ise.log.ad.srv
cisco_ise.log.ad.srv.query
cisco_ise.log.ad.srv.record
cisco_ise.log.adapter_instance
cisco_ise.log.adapter_instance.name
cisco_ise.log.adapter_instance.uuid
cisco_ise.log.admin
cisco_ise.log.admin.interface
cisco_ise.log.admin.session
cisco_ise.log.airespace
cisco_ise.log.airespace.wlan
cisco_ise.log.airespace.wlan.id
cisco_ise.log.allow
cisco_ise.log.allow.easy
cisco_ise.log.allow.easy.wired
cisco_ise.log.allow.easy.wired.session
cisco_ise.log.allowed_protocol
cisco_ise.log.allowed_protocol.matched
cisco_ise.log.allowed_protocol.matched.rule
cisco_ise.log.assigned_targets
cisco_ise.log.auth
cisco_ise.log.auth.policy
cisco_ise.log.auth.policy.matched
cisco_ise.log.auth.policy.matched.rule
cisco_ise.log.authen_method
cisco_ise.log.authentication
cisco_ise.log.authentication.identity_store
cisco_ise.log.authentication.method
cisco_ise.log.authentication.status
cisco_ise.log.average
cisco_ise.log.average.radius
cisco_ise.log.average.radius.request
cisco_ise.log.average.radius.request.latency
cisco_ise.log.average.tacacs
cisco_ise.log.average.tacacs.request
cisco_ise.log.average.tacacs.request.latency
cisco_ise.log.avpair
cisco_ise.log.avpair.affected-dn
cisco_ise.log.avpair.change-set
cisco_ise.log.avpair.disc
cisco_ise.log.avpair.disc.cause
cisco_ise.log.avpair.disc.cause_ext
cisco_ise.log.avpair.elapsed_time
cisco_ise.log.avpair.event
cisco_ise.log.avpair.ios-version
cisco_ise.log.avpair.log-id
cisco_ise.log.avpair.login-ip-addr-host
cisco_ise.log.avpair.login-service
cisco_ise.log.avpair.login-tcp-port
cisco_ise.log.avpair.pre_session_time
cisco_ise.log.avpair.priv_lvl
cisco_ise.log.avpair.reason
cisco_ise.log.avpair.reload-reason
cisco_ise.log.avpair.reload-user
cisco_ise.log.avpair.session-id
cisco_ise.log.avpair.severity
cisco_ise.log.avpair.start_time
cisco_ise.log.avpair.stop_time
cisco_ise.log.avpair.task_id
cisco_ise.log.avpair.timezone
cisco_ise.log.called_station
cisco_ise.log.called_station.id
cisco_ise.log.calling_station
cisco_ise.log.calling_station.id
cisco_ise.log.calling_station_id
cisco_ise.log.category
cisco_ise.log.category.name
cisco_ise.log.cause
cisco_ise.log.cisco_av_pair
cisco_ise.log.cisco_av_pair.AAA:service-type
cisco_ise.log.cisco_av_pair.AuthenticationIdentityStore
cisco_ise.log.cisco_av_pair.FQSubjectName
cisco_ise.log.cisco_av_pair.UniqueSubjectID
cisco_ise.log.cisco_av_pair.aaa:event
cisco_ise.log.cisco_av_pair.aaa:service
cisco_ise.log.cisco_av_pair.addrv6
cisco_ise.log.cisco_av_pair.audit-session-id
cisco_ise.log.cisco_av_pair.client-iif-id
cisco_ise.log.cisco_av_pair.coa-push
cisco_ise.log.cisco_av_pair.cts-device-capability
cisco_ise.log.cisco_av_pair.cts-environment-data
cisco_ise.log.cisco_av_pair.cts-environment-version
cisco_ise.log.cisco_av_pair.cts-pac-opaque
cisco_ise.log.cisco_av_pair.cts-rbacl
cisco_ise.log.cisco_av_pair.cts-rbacl-source-list
cisco_ise.log.cisco_av_pair.cts-security-group-table
cisco_ise.log.cisco_av_pair.cts-server-list
cisco_ise.log.cisco_av_pair.cts:security-group-tag
cisco_ise.log.cisco_av_pair.device-uid-global
cisco_ise.log.cisco_av_pair.ip:source-ip
cisco_ise.log.cisco_av_pair.mdm-tlv
cisco_ise.log.cisco_av_pair.mdm-tlv.ac-user-agent
cisco_ise.log.cisco_av_pair.mdm-tlv.computer-name
cisco_ise.log.cisco_av_pair.mdm-tlv.device-mac
cisco_ise.log.cisco_av_pair.mdm-tlv.device-platform
cisco_ise.log.cisco_av_pair.mdm-tlv.device-platform-version
cisco_ise.log.cisco_av_pair.mdm-tlv.device-public-mac
cisco_ise.log.cisco_av_pair.mdm-tlv.device-type
cisco_ise.log.cisco_av_pair.mdm-tlv.device-uid
cisco_ise.log.cisco_av_pair.mdm-tlv.device-uid-global
cisco_ise.log.cisco_av_pair.method
cisco_ise.log.cisco_av_pair.policy:command
cisco_ise.log.cisco_av_pair.service-type
cisco_ise.log.cisco_av_pair.subscriber:command
cisco_ise.log.cisco_av_pair.subscriber:reauthenticate-type
cisco_ise.log.cisco_av_pair.vlan-id
cisco_ise.log.class
cisco_ise.log.client
cisco_ise.log.client.latency
cisco_ise.log.cmdset
cisco_ise.log.component
cisco_ise.log.config_change
cisco_ise.log.config_change.data
cisco_ise.log.config_version
cisco_ise.log.config_version.id
cisco_ise.log.connectivity
cisco_ise.log.cpm
cisco_ise.log.cpm.session
cisco_ise.log.cpm.session.id
cisco_ise.log.currentid
cisco_ise.log.currentid.store_name
cisco_ise.log.delta
cisco_ise.log.delta.radius
cisco_ise.log.delta.radius.request
cisco_ise.log.delta.radius.request.count
cisco_ise.log.delta.tacacs
cisco_ise.log.delta.tacacs.request
cisco_ise.log.delta.tacacs.request.count
cisco_ise.log.detailed_info
cisco_ise.log.details
cisco_ise.log.device
cisco_ise.log.device.name
cisco_ise.log.device.registration_status
cisco_ise.log.device.type
cisco_ise.log.dtls_support
cisco_ise.log.eap
cisco_ise.log.eap.authentication
cisco_ise.log.eap.chaining_result
cisco_ise.log.eap.tunnel
cisco_ise.log.eap_key
cisco_ise.log.eap_key.name
cisco_ise.log.enable
cisco_ise.log.enable.flag
cisco_ise.log.endpoint
cisco_ise.log.endpoint.coa
cisco_ise.log.endpoint.mac
cisco_ise.log.endpoint.mac.address
cisco_ise.log.endpoint.policy
cisco_ise.log.endpoint.profiler
cisco_ise.log.endpoint.purge
cisco_ise.log.endpoint.purge.id
cisco_ise.log.endpoint.purge.rule
cisco_ise.log.endpoint.purge.scheduletype
cisco_ise.log.ep
cisco_ise.log.ep.identity_group
cisco_ise.log.ep.mac
cisco_ise.log.ep.mac.address
cisco_ise.log.error
cisco_ise.log.error.message
cisco_ise.log.error_message
cisco_ise.log.event
cisco_ise.log.event.timestamp
cisco_ise.log.failure
cisco_ise.log.failure.flag
cisco_ise.log.failure.reason
cisco_ise.log.failure_reason
cisco_ise.log.feed_service
cisco_ise.log.feed_service.feed
cisco_ise.log.feed_service.feed.name
cisco_ise.log.feed_service.feed.version
cisco_ise.log.feed_service.host
cisco_ise.log.feed_service.port
cisco_ise.log.feed_service.query
cisco_ise.log.feed_service.query.from_time
cisco_ise.log.feed_service.query.to_time
cisco_ise.log.file
cisco_ise.log.file.name
cisco_ise.log.first_name
cisco_ise.log.framed
cisco_ise.log.framed.ip
cisco_ise.log.framed.mtu
cisco_ise.log.groups
cisco_ise.log.groups.process_failure
cisco_ise.log.guest
cisco_ise.log.guest.user
cisco_ise.log.guest.user.name
cisco_ise.log.identity
cisco_ise.log.identity.group
cisco_ise.log.identity.policy
cisco_ise.log.identity.policy.matched
cisco_ise.log.identity.policy.matched.rule
cisco_ise.log.identity.selection
cisco_ise.log.identity.selection.matched
cisco_ise.log.identity.selection.matched.rule
cisco_ise.log.installed
cisco_ise.log.ipsec
cisco_ise.log.is_third_party_device_flow
cisco_ise.log.ise
cisco_ise.log.ise.policy
cisco_ise.log.ise.policy.set_name
cisco_ise.log.last_name
cisco_ise.log.local_logging
cisco_ise.log.location
cisco_ise.log.log_details
cisco_ise.log.log_error
cisco_ise.log.log_error.message
cisco_ise.log.log_severity_level
cisco_ise.log.logger
cisco_ise.log.logger.name
cisco_ise.log.message
cisco_ise.log.message.code
cisco_ise.log.message.description
cisco_ise.log.message.id
cisco_ise.log.message.text
cisco_ise.log.misconfigured
cisco_ise.log.misconfigured.client
cisco_ise.log.misconfigured.client.fix
cisco_ise.log.misconfigured.client.fix.reason
cisco_ise.log.model
cisco_ise.log.model.name
cisco_ise.log.nas
cisco_ise.log.nas.identifier
cisco_ise.log.nas.ip
cisco_ise.log.nas.port
cisco_ise.log.nas.port.id
cisco_ise.log.nas.port.number
cisco_ise.log.nas.port.type
cisco_ise.log.nas_identifier
cisco_ise.log.nas_ip_address
cisco_ise.log.network
cisco_ise.log.network.device
cisco_ise.log.network.device.groups
cisco_ise.log.network.device.name
cisco_ise.log.network.device.profile
cisco_ise.log.network.device.profile_id
cisco_ise.log.network.device.profile_name
cisco_ise.log.network_device_ip
cisco_ise.log.network_device_name
cisco_ise.log.object
cisco_ise.log.object.internal
cisco_ise.log.object.internal.id
cisco_ise.log.object.name
cisco_ise.log.object.type
cisco_ise.log.objects
cisco_ise.log.objects.purged
cisco_ise.log.openssl
cisco_ise.log.openssl.error
cisco_ise.log.openssl.error.message
cisco_ise.log.openssl.error.stack
cisco_ise.log.operating
cisco_ise.log.operating.system
cisco_ise.log.operation
cisco_ise.log.operation.id
cisco_ise.log.operation.status
cisco_ise.log.operation.type
cisco_ise.log.operation_counters
cisco_ise.log.operation_counters.counters
cisco_ise.log.operation_counters.original
cisco_ise.log.operation_message
cisco_ise.log.operation_message.text
cisco_ise.log.original
cisco_ise.log.original.user
cisco_ise.log.original.user.name
cisco_ise.log.policy
cisco_ise.log.policy.type
cisco_ise.log.port
cisco_ise.log.portal
cisco_ise.log.portal.name
cisco_ise.log.posture
cisco_ise.log.posture.admin_password
cisco_ise.log.posture.admin_password.local
cisco_ise.log.posture.admin_password.local.check
cisco_ise.log.posture.admin_password.local.failed_conditions
cisco_ise.log.posture.admin_password.local.passed_conditions
cisco_ise.log.posture.admin_password.local.skipped_conditions
cisco_ise.log.posture.admin_password.local.status
cisco_ise.log.posture.admin_password.status
cisco_ise.log.posture.agent
cisco_ise.log.posture.agent.version
cisco_ise.log.posture.app_whitelist
cisco_ise.log.posture.app_whitelist.status
cisco_ise.log.posture.app_whitelist.whitelisting
cisco_ise.log.posture.app_whitelist.whitelisting.check
cisco_ise.log.posture.app_whitelist.whitelisting.failed_conditions
cisco_ise.log.posture.app_whitelist.whitelisting.passed_conditions
cisco_ise.log.posture.app_whitelist.whitelisting.skipped_conditions
cisco_ise.log.posture.app_whitelist.whitelisting.status
cisco_ise.log.posture.assessment
cisco_ise.log.posture.assessment.status
cisco_ise.log.posture.av
cisco_ise.log.posture.av.anti_malware
cisco_ise.log.posture.av.anti_malware.check
cisco_ise.log.posture.av.anti_malware.failed_conditions
cisco_ise.log.posture.av.anti_malware.passed_conditions
cisco_ise.log.posture.av.anti_malware.skipped_conditions
cisco_ise.log.posture.av.anti_malware.status
cisco_ise.log.posture.av.status
cisco_ise.log.posture.data_loss
cisco_ise.log.posture.data_loss.dlp
cisco_ise.log.posture.data_loss.dlp.failed_conditions
cisco_ise.log.posture.data_loss.dlp.passed_conditions
cisco_ise.log.posture.data_loss.dlp.skipped_conditions
cisco_ise.log.posture.data_loss.dlp.status
cisco_ise.log.posture.data_loss.status
cisco_ise.log.posture.disc_encryption
cisco_ise.log.posture.disc_encryption.bitlocker
cisco_ise.log.posture.disc_encryption.bitlocker.check
cisco_ise.log.posture.disc_encryption.bitlocker.failed_conditions
cisco_ise.log.posture.disc_encryption.bitlocker.passed_conditions
cisco_ise.log.posture.disc_encryption.bitlocker.skipped_conditions
cisco_ise.log.posture.disc_encryption.bitlocker.status
cisco_ise.log.posture.disc_encryption.status
cisco_ise.log.posture.dlp
cisco_ise.log.posture.dlp.dlp
cisco_ise.log.posture.dlp.dlp.check
cisco_ise.log.posture.domain_registry
cisco_ise.log.posture.domain_registry.USAFRICOM
cisco_ise.log.posture.domain_registry.USAFRICOM.check
cisco_ise.log.posture.domain_registry.USAFRICOM.passed_conditions
cisco_ise.log.posture.domain_registry.USAFRICOM.status
cisco_ise.log.posture.domain_registry.status
cisco_ise.log.posture.firewall
cisco_ise.log.posture.firewall.firewall
cisco_ise.log.posture.firewall.firewall.check
cisco_ise.log.posture.firewall.firewall.failed_conditions
cisco_ise.log.posture.firewall.firewall.passed_conditions
cisco_ise.log.posture.firewall.firewall.skipped_conditions
cisco_ise.log.posture.firewall.firewall.status
cisco_ise.log.posture.firewall.status
cisco_ise.log.posture.mass_storage
cisco_ise.log.posture.mass_storage.status
cisco_ise.log.posture.mass_storage.usb_block
cisco_ise.log.posture.mass_storage.usb_block.check
cisco_ise.log.posture.mass_storage.usb_block.failed_conditions
cisco_ise.log.posture.mass_storage.usb_block.passed_conditions
cisco_ise.log.posture.mass_storage.usb_block.skipped_conditions
cisco_ise.log.posture.mass_storage.usb_block.status
cisco_ise.log.posture.patch_compliance
cisco_ise.log.posture.patch_compliance.pa_running
cisco_ise.log.posture.patch_compliance.pa_running.check
cisco_ise.log.posture.patch_compliance.pa_running.failed_conditions
cisco_ise.log.posture.patch_compliance.pa_running.passed_conditions
cisco_ise.log.posture.patch_compliance.pa_running.skipped_conditions
cisco_ise.log.posture.patch_compliance.pa_running.status
cisco_ise.log.posture.patch_compliance.pa_version
cisco_ise.log.posture.patch_compliance.pa_version.check
cisco_ise.log.posture.patch_compliance.pa_version.failed_conditions
cisco_ise.log.posture.patch_compliance.pa_version.passed_conditions
cisco_ise.log.posture.patch_compliance.pa_version.skipped_conditions
cisco_ise.log.posture.patch_compliance.pa_version.status
cisco_ise.log.posture.patch_compliance.status
cisco_ise.log.posture.report
cisco_ise.log.posture.status
cisco_ise.log.posture.stig_compliance
cisco_ise.log.posture.stig_compliance.pa_running
cisco_ise.log.posture.stig_compliance.pa_running.check
cisco_ise.log.posture.stig_compliance.pa_running.failed_conditions
cisco_ise.log.posture.stig_compliance.pa_running.passed_conditions
cisco_ise.log.posture.stig_compliance.pa_running.skipped_conditions
cisco_ise.log.posture.stig_compliance.pa_running.status
cisco_ise.log.posture.stig_compliance.pa_version
cisco_ise.log.posture.stig_compliance.pa_version.check
cisco_ise.log.posture.stig_compliance.pa_version.failed_conditions
cisco_ise.log.posture.stig_compliance.pa_version.passed_conditions
cisco_ise.log.posture.stig_compliance.pa_version.skipped_conditions
cisco_ise.log.posture.stig_compliance.pa_version.status
cisco_ise.log.pra
cisco_ise.log.pra.action
cisco_ise.log.pra.enforcement
cisco_ise.log.pra.enforcement.flag
cisco_ise.log.pra.grace
cisco_ise.log.pra.grace.time
cisco_ise.log.pra.interval
cisco_ise.log.privilege
cisco_ise.log.privilege.level
cisco_ise.log.probe
cisco_ise.log.profiler
cisco_ise.log.profiler.server
cisco_ise.log.protocol
cisco_ise.log.psn
cisco_ise.log.psn.hostname
cisco_ise.log.radius
cisco_ise.log.radius.flow
cisco_ise.log.radius.flow.type
cisco_ise.log.radius.packet
cisco_ise.log.radius.packet.type
cisco_ise.log.radius_identifier
cisco_ise.log.radius_packet
cisco_ise.log.radius_packet.type
cisco_ise.log.request
cisco_ise.log.request.latency
cisco_ise.log.request.received_time
cisco_ise.log.request.time
cisco_ise.log.request_response
cisco_ise.log.request_response.type
cisco_ise.log.response
cisco_ise.log.segment
cisco_ise.log.segment.number
cisco_ise.log.segment.total
cisco_ise.log.selected
cisco_ise.log.selected.access
cisco_ise.log.selected.access.service
cisco_ise.log.selected.authentication
cisco_ise.log.selected.authentication.identity_stores
cisco_ise.log.selected.authorization
cisco_ise.log.selected.authorization.profiles
cisco_ise.log.sequence
cisco_ise.log.sequence.number
cisco_ise.log.server
cisco_ise.log.server.name
cisco_ise.log.server.type
cisco_ise.log.service
cisco_ise.log.service.argument
cisco_ise.log.service.name
cisco_ise.log.service.type
cisco_ise.log.session
cisco_ise.log.session.timeout
cisco_ise.log.severity
cisco_ise.log.severity.level
cisco_ise.log.software
cisco_ise.log.software.version
cisco_ise.log.state
cisco_ise.log.static
cisco_ise.log.static.assignment
cisco_ise.log.status
cisco_ise.log.step
cisco_ise.log.step_data
cisco_ise.log.step_latency
cisco_ise.log.sysstats
cisco_ise.log.sysstats.acs
cisco_ise.log.sysstats.acs.process
cisco_ise.log.sysstats.acs.process.health
cisco_ise.log.sysstats.cpu
cisco_ise.log.sysstats.cpu.count
cisco_ise.log.sysstats.process_memory_mb
cisco_ise.log.sysstats.utilization
cisco_ise.log.sysstats.utilization.cpu
cisco_ise.log.sysstats.utilization.disk
cisco_ise.log.sysstats.utilization.disk.io
cisco_ise.log.sysstats.utilization.disk.space
cisco_ise.log.sysstats.utilization.load_avg
cisco_ise.log.sysstats.utilization.memory
cisco_ise.log.sysstats.utilization.network
cisco_ise.log.system
cisco_ise.log.system.domain
cisco_ise.log.system.name
cisco_ise.log.system.name.text
cisco_ise.log.system.user
cisco_ise.log.system.user.domain
cisco_ise.log.system.user.name
cisco_ise.log.system.user.name.text
cisco_ise.log.tls
cisco_ise.log.tls.cipher
cisco_ise.log.tls.version
cisco_ise.log.total
cisco_ise.log.total.authen
cisco_ise.log.total.authen.latency
cisco_ise.log.total.failed_attempts
cisco_ise.log.total.failed_time
cisco_ise.log.tunnel
cisco_ise.log.tunnel.medium
cisco_ise.log.tunnel.medium.type
cisco_ise.log.tunnel.private
cisco_ise.log.tunnel.private.group_id
cisco_ise.log.tunnel.type
cisco_ise.log.type
cisco_ise.log.undefined_52
cisco_ise.log.usecase
cisco_ise.log.user
cisco_ise.log.user.type
cisco_ise.log.user_agreement
cisco_ise.log.user_agreement.status
cisco_ise.log.workflow
cisco_ise.posture_check
cisco_ise.posture_check.failed
cisco_ise.posture_check.passed
cisco_nexus
cisco_nexus.log
cisco_nexus.log.command
cisco_nexus.log.description
cisco_nexus.log.euid
cisco_nexus.log.facility
cisco_nexus.log.interface
cisco_nexus.log.interface.mode
cisco_nexus.log.interface.name
cisco_nexus.log.ip_address
cisco_nexus.log.line_protocol_state
cisco_nexus.log.logname
cisco_nexus.log.network
cisco_nexus.log.network.egress_interface
cisco_nexus.log.network.ingress_interface
cisco_nexus.log.operating_value
cisco_nexus.log.operational
cisco_nexus.log.operational.duplex_mode
cisco_nexus.log.operational.receive_flow_control_state
cisco_nexus.log.operational.speed
cisco_nexus.log.operational.transmit_flow_control_state
cisco_nexus.log.priority_number
cisco_nexus.log.pwd
cisco_nexus.log.rhost
cisco_nexus.log.ruser
cisco_nexus.log.sequence_number
cisco_nexus.log.severity
cisco_nexus.log.slot_number
cisco_nexus.log.standby
cisco_nexus.log.state
cisco_nexus.log.switch_name
cisco_nexus.log.syslog_time
cisco_nexus.log.terminal
cisco_nexus.log.threshold_value
cisco_nexus.log.time
cisco_nexus.log.timezone
cisco_nexus.log.tty
cisco_nexus.log.type
cisco_nexus.log.uid
client
client.address
client.as
client.as.number
client.as.organization
client.as.organization.name
client.as.organization.name.text
client.bytes
client.domain
client.geo
client.geo.city_name
client.geo.continent_code
client.geo.continent_name
client.geo.country_iso_code
client.geo.country_name
client.geo.location
client.geo.name
client.geo.postal_code
client.geo.region_iso_code
client.geo.region_name
client.geo.timezone
client.ip
client.mac
client.nat
client.nat.ip
client.nat.port
client.packets
client.port
client.process
client.process.args
client.process.executable
client.process.name
client.process.start
client.process.working_directory
client.user
client.user.domain
client.user.email
client.user.name
client.user.name.text
cloud
cloud.account
cloud.account.id
cloud.account.name
cloud.availability_zone
cloud.image
cloud.image.id
cloud.instance
cloud.instance.id
cloud.instance.name
cloud.machine
cloud.machine.type
cloud.project
cloud.project.id
cloud.provider
cloud.region
cloud.service
cloud.service.name
completed_at
completionDate
component
component.binary
component.dataset
component.id
component.old_state
component.state
component.type
container
container.disk
container.disk.read
container.disk.read.bytes
container.disk.write
container.disk.write.bytes
container.id
container.image
container.image.hash
container.image.hash.all
container.image.name
container.image.tag
container.name
container.network
container.network.egress
container.network.egress.bytes
container.network.ingress
container.network.ingress.bytes
container.runtime
container.security_context
container.security_context.privileged
context
count
cyberarkpas
cyberarkpas.audit
cyberarkpas.audit.action
cyberarkpas.audit.ca_properties
cyberarkpas.audit.ca_properties.address
cyberarkpas.audit.ca_properties.cpm_disabled
cyberarkpas.audit.ca_properties.cpm_error_details
cyberarkpas.audit.ca_properties.cpm_status
cyberarkpas.audit.ca_properties.creation_method
cyberarkpas.audit.ca_properties.customer
cyberarkpas.audit.ca_properties.database
cyberarkpas.audit.ca_properties.device_type
cyberarkpas.audit.ca_properties.dual_account_status
cyberarkpas.audit.ca_properties.group_name
cyberarkpas.audit.ca_properties.in_process
cyberarkpas.audit.ca_properties.index
cyberarkpas.audit.ca_properties.last_fail_date
cyberarkpas.audit.ca_properties.last_success_change
cyberarkpas.audit.ca_properties.last_success_reconciliation
cyberarkpas.audit.ca_properties.last_success_verification
cyberarkpas.audit.ca_properties.last_task
cyberarkpas.audit.ca_properties.logon_domain
cyberarkpas.audit.ca_properties.other
cyberarkpas.audit.ca_properties.policy_id
cyberarkpas.audit.ca_properties.port
cyberarkpas.audit.ca_properties.privcloud
cyberarkpas.audit.ca_properties.reset_immediately
cyberarkpas.audit.ca_properties.retries_count
cyberarkpas.audit.ca_properties.sequence_id
cyberarkpas.audit.ca_properties.tags
cyberarkpas.audit.ca_properties.user_dn
cyberarkpas.audit.ca_properties.user_name
cyberarkpas.audit.ca_properties.virtual_username
cyberarkpas.audit.category
cyberarkpas.audit.desc
cyberarkpas.audit.extra_details
cyberarkpas.audit.extra_details.ad_process_id
cyberarkpas.audit.extra_details.ad_process_name
cyberarkpas.audit.extra_details.application_type
cyberarkpas.audit.extra_details.command
cyberarkpas.audit.extra_details.connection_component_id
cyberarkpas.audit.extra_details.dst_host
cyberarkpas.audit.extra_details.logon_account
cyberarkpas.audit.extra_details.managed_account
cyberarkpas.audit.extra_details.other
cyberarkpas.audit.extra_details.process_id
cyberarkpas.audit.extra_details.process_name
cyberarkpas.audit.extra_details.protocol
cyberarkpas.audit.extra_details.psmid
cyberarkpas.audit.extra_details.session_duration
cyberarkpas.audit.extra_details.session_id
cyberarkpas.audit.extra_details.src_host
cyberarkpas.audit.extra_details.username
cyberarkpas.audit.file
cyberarkpas.audit.gateway_station
cyberarkpas.audit.hostname
cyberarkpas.audit.iso_timestamp
cyberarkpas.audit.issuer
cyberarkpas.audit.location
cyberarkpas.audit.message
cyberarkpas.audit.message_id
cyberarkpas.audit.product
cyberarkpas.audit.pvwa_details
cyberarkpas.audit.raw
cyberarkpas.audit.reason
cyberarkpas.audit.rfc5424
cyberarkpas.audit.safe
cyberarkpas.audit.severity
cyberarkpas.audit.source_user
cyberarkpas.audit.station
cyberarkpas.audit.target_user
cyberarkpas.audit.timestamp
cyberarkpas.audit.vendor
cyberarkpas.audit.version
cybersecurityServiceProviderValidationDate
data_stream
data_stream.dataset
data_stream.namespace
data_stream.type
dataset
dataset.name
dataset.namespace
dataset.type
daysSinceCreated
destination
destination.address
destination.as
destination.as.number
destination.as.organization
destination.as.organization.name
destination.as.organization.name.text
destination.bytes
destination.domain
destination.file
destination.file.path
destination.geo
destination.geo.city_name
destination.geo.continent_code
destination.geo.continent_name
destination.geo.country_iso_code
destination.geo.country_name
destination.geo.location
destination.geo.name
destination.geo.postal_code
destination.geo.region_iso_code
destination.geo.region_name
destination.geo.timezone
destination.host
```

---

<!-- DCOIR_SOURCE_END {"id":"knowledge.reference.elastic_fields","sha256":"423c6ad263ec597e7f0c13e78b74626ca4efe443a16d410e5aa00ab416248c32"} -->

<!-- DCOIR_SOURCE_BEGIN {"bytes":15674,"git_blob_sha":"bd0ec9761e7afcb1a2fcd7bcae714e8f72de9d2e","id":"knowledge.reference.elastic_actions","path":"knowledge/Knowledge - Reference - Elastic Response Actions Reference.md","sha256":"24e111e712b295e09145afe327cd63769d93d59786ccc57926a9909ba83855f1"} -->
# Knowledge - Reference - Elastic Response Actions Reference

_Governed reference for native Elastic response-action syntax_

**Summary:** Use this page when the next analyst action should be a native Elastic response action. Preserve native response-action syntax directly, and do not wrap native response actions inside `execute`.

---

## Reference source

The material below is preserved from the approved response-actions source markdown. Keep command names, parameters, privileges, and layout exact when using it as a reference.

---

# Endpoint response actions

**IMPORTANT**: This documentation is no longer updated. Refer to [Elastic's version policy](https://www.elastic.co/support/eol) and the [latest documentation](https://www.elastic.co/docs/solutions/security/endpoint-response-actions).

The response console allows you to perform response actions on an endpoint using a terminal-like interface. You can enter action commands and get near-instant feedback on them. Actions are also recorded in the endpoint’s [response actions history](https://www.elastic.co/guide/en/security/8.19/response-actions.html#actions-log "Response actions history") for reference.

Response actions are supported on all endpoint platforms (Linux, macOS, and Windows).

**Requirements**

- Response actions and the response console UI are [Enterprise subscription](https://www.elastic.co/pricing) features.
- Endpoints must have Elastic Agent version 8.4 or higher installed with the Elastic Defend integration to receive response actions.
- Some response actions require specific [privileges](https://www.elastic.co/guide/en/security/8.19/endpoint-management-req.html "Elastic Defend feature privileges"), indicated below. These are required to perform actions both in the response console and in other areas of the Elastic Security app (such as isolating a host from a detection alert).
- Users must have privileges for at least one response action to access the response console.

**Interface description:** The response console page shows the selected endpoint, its health status, a **Response actions history** button, a **Help** control, an empty console output area, and a **Submit response action** input field at the bottom where commands are entered.

Launch the response console from any of the following places in Elastic Security:

- **Endpoints** page → **Actions** menu (**…**) → **Respond**
- Endpoint details flyout → **Take action** → **Respond**
- Alert or event details flyout → **Take action** → **Respond**
- Host details page → **Respond**

To perform an action on the endpoint, enter a [response action command](https://www.elastic.co/guide/en/security/8.19/response-actions.html#response-action-commands "Response action commands") in the input area at the bottom of the console, then press **Return**. Output from the action is displayed in the console.

If a host is unavailable, pending actions will execute once the host comes online. Pending actions expire after two weeks and can be tracked in the response actions history.

> **Note:**
>
> Some response actions may take a few seconds to complete. Once you enter a command, you can immediately enter another command while the previous action is running.

Activity in the response console is persistent, so you can navigate away from the page and any pending actions you’ve submitted will continue to run. To confirm that an action completed, return to the response console to view the console output or check the [response actions history](https://www.elastic.co/guide/en/security/8.19/response-actions.html#actions-log "Response actions history").

> **Important:**
>
> Once you submit a response action, you can’t cancel it, even if the action is pending for an offline host.

## Response action commands

The following response action commands are available in the response console.

### `isolate`

[Isolate the host](https://www.elastic.co/guide/en/security/8.19/host-isolation-ov.html "Isolate a host"), blocking communication with other hosts on the network.

Required privilege: **Host Isolation**

Example: `isolate --comment "Isolate host related to detection alerts"`

### `release`

Release an isolated host, allowing it to communicate with the network again.

Required privilege: **Host Isolation**

Example: `release --comment "Release host, everything looks OK"`

### `status`

Show information about the host’s status, including: Elastic Agent status and version, the Elastic Defend integration’s policy status, and when the host was last active.

### `processes`

Show a list of all processes running on the host. This action may take a minute or so to complete.

Required privilege: **Process Operations**

> **Tip:**
>
> Use this command to get current PID or entity ID values, which are required for other response actions such as `kill-process` and `suspend-process`.
>
> Entity IDs may be more reliable than PIDs, because entity IDs are unique values on the host, while PID values can be reused by the operating system.

> **Note:**
>
> Running this command on third-party-protected hosts might return the process list in a different format. Refer to [*Third-party response actions*](https://www.elastic.co/guide/en/security/8.19/third-party-actions.html "Third-party response actions") for more information.

### `kill-process`

Terminate a process. You must include one of the following parameters to identify the process to terminate:

- `--pid`: A process ID (PID) representing the process to terminate.
- `--entityId`: An entity ID representing the process to terminate.

Required privilege: **Process Operations**

Example: `kill-process --pid 123 --comment "Terminate suspicious process"`

> **Note:**
>
> For SentinelOne-enrolled hosts, you must use the parameter `--processName` to identify the process to terminate. `--pid` and `--entityId` are not supported.
>
> Example: `kill-process --processName cat --comment "Terminate suspicious process"`

### `suspend-process`

Suspend a process. You must include one of the following parameters to identify the process to suspend:

- `--pid`: A process ID (PID) representing the process to suspend.
- `--entityId`: An entity ID representing the process to suspend.

Required privilege: **Process Operations**

Example: `suspend-process --pid 123 --comment "Suspend suspicious process"`

### `get-file`

Retrieve a file from a host. Files are downloaded in a password-protected `.zip` archive to prevent the file from running. Use password `elastic` to open the `.zip` in a safe environment.

> **Note:**
>
> Files retrieved from third-party-protected hosts require a different password. Refer to [*Third-party response actions*](https://www.elastic.co/guide/en/security/8.19/third-party-actions.html "Third-party response actions") for your system’s password.

You must include the following parameter to specify the file’s location on the host:

- `--path`: The file’s full path (including the file name).

Required privilege: **File Operations**

Example: `get-file --path "/full/path/to/file.txt" --comment "Possible malware"`

> **Note:**
>
> The maximum file size that can be retrieved using `get-file` is `104857600` bytes, or 100 MB.

> **Tip:**
>
> You can use the [Osquery manager integration](https://www.elastic.co/guide/en/security/8.19/use-osquery.html "Osquery") to query a host’s operating system and gain insight into its files and directories, then use `get-file` to retrieve specific files.

> **Note:**
>
> When Elastic Defend prevents file activity due to [malware prevention](https://www.elastic.co/guide/en/security/8.19/configure-endpoint-integration-policy.html#malware-protection "Malware protection"), the file is quarantined on the host and a malware prevention alert is created. To retrieve this file with `get-file`, copy the path from the alert’s **Quarantined file path** field (`file.Ext.quarantine_path`), which appears under **Highlighted fields** in the alert details flyout. Then paste the value into the `--path` parameter.

### `execute`

Run a shell command on the host. The command’s output and any errors appear in the response console, up to 2000 characters. The complete output (stdout and stderr) are also saved to a downloadable `.zip` archive (password: `elastic`). Use these parameters:

- `--command`: (Required) A shell command to run on the host. The command must be supported by `bash` for Linux and macOS hosts, and `cmd.exe` for Windows.

  > **Note:**
  >
  > - Multiple consecutive dashes in the value must be escaped; single dashes do not need to be escaped. For example, to represent a directory named `/opt/directory--name`, use the following: `/opt/directory\-\-name`.
  > - You can use quotation marks without escaping. For example:
  >   `execute --command "cd "C:\Program Files\directory""`
- `--timeout`: (Optional) How long the host should wait for the command to complete. Use `h` for hours, `m` for minutes, `s` for seconds (for example, `2s` is two seconds). If no timeout is specified, it defaults to four hours.

Required privilege: **Execute Operations**

Example: `execute --command "ls -al" --timeout 2s --comment "Get list of all files"`

> **Warning:**
>
> This response action runs commands on the host using the same user account running the Elastic Defend integration, which normally has full control over the system. Be careful with any commands that could cause irrevocable changes.

### `upload`

Upload a file to the host. The file is saved to the location on the host where Elastic Endpoint is installed. After you run the command, the full path is returned in the console for reference. Use these parameters:

- `--file`: (Required) The file to send to the host. As soon as you type this parameter, a popup appears — select it to navigate to the file, or drag and drop the file onto the popup.
- `--overwrite`: (Optional) Overwrite the file on the host if it already exists.

Required privilege: **File Operations**

Example: `upload --file --comment "Upload remediation script"`

> **Tip:**
>
> You can follow this with the `execute` response action to upload and run scripts for mitigation or other purposes.

> **Note:**
>
> The default file size maximum is 25 MB, configurable in `kibana.yml` with the `xpack.securitySolution.maxUploadResponseActionFileBytes` setting. You must enter the value in bytes (the maximum is `104857600` bytes, or 100 MB).

### `scan`

Scan a specific file or directory on the host for malware. This uses the [malware protection settings](https://www.elastic.co/guide/en/security/8.19/configure-endpoint-integration-policy.html#malware-protection "Malware protection") (such as **Detect** or **Prevent** options, or enabling the blocklist) as configured in the host’s associated Elastic Defend integration policy. Use these parameters:

- `--path`: (Required) The absolute path to a file or directory to be scanned.

Required privilege: **Scan Operations**

Example: `scan --path "/Users/username/Downloads" --comment "Scan Downloads folder for malware"`

> **Note:**
>
> Scanning can take longer for directories containing a lot of files.

### `runscript`

Run a script on a host.

#### CrowdStrike

For CrowdStrike, you must include one of the following parameters to identify the script you want to run:

- `--Raw`: The full script content provided directly as a string.
- `--CloudFile`: The name of the script stored in a cloud storage location. When using this parameter, select from a list of saved custom scripts.
- `--HostPath`: The absolute or relative file path of the script located on the host machine.

You can also use these optional parameters:

- `--CommandLine`: Additional command-line arguments passed to the script to customize its execution.
- `--Timeout`: The maximum duration, in seconds, that the script can run before it’s forcibly stopped. If no timeout is specified, it defaults to 60 seconds.

Required privilege: **Execute Operations**

Examples:

`runscript --CloudFile="CloudScript1.ps1" --CommandLine="-Verbose true" --Timeout=180`

````text
runscript --Raw=```Get-ChildItem.```
````

`runscript --HostPath="C:\temp\LocalScript.ps1" --CommandLine="-Verbose true"`

#### Microsoft Defender for Endpoint

For Microsoft Defender for Endpoint, you must include the following parameter to identify the script you want to run:

- `--ScriptName`: The name of the script stored in a cloud storage location. Select from a list of saved custom scripts.

You can also use this optional parameter:

- `--Args`: Additional command-line arguments passed to the script to customize its execution.

  > **Note:**
  >
  > The response console does not support double-dash (`--`) syntax within the `--Args` parameter.

Required privilege: **Execute Operations**

Example: `runscript --ScriptName="Script2.sh" --Args="-Verbose true"`

## Supporting commands and parameters

### `--comment`

Add to a command to include a comment explaining or describing the action. Comments are included in the response actions history.

### `--help`

Add to a command to get help for that command.

Example: `isolate --help`

### `clear`

Clear all output from the response console.

### `help`

List supported commands in the console output area.

> **Tip:**
>
> You can also get a list of commands in the [Help panel](https://www.elastic.co/guide/en/security/8.19/response-actions.html#help-panel "Help panel"), which stays on the screen independently of the output area.

## Help panel

Click the circular Help icon labeled **Help** in the upper-right to open the **Help** panel, which lists available response action commands and parameters as a reference.

> **Note:**
>
> This panel displays only the response actions that the user has privileges to perform.

**Help panel description:** The Help panel lists available response action commands with a plus-sign add button beside each command. Visible examples include `isolate`, `release`, `status`, `processes`, `kill-process --pid`, `suspend-process --pid`, `get-file --path`, `execute --command`, `upload --file`, and `scan --path`. It also lists supporting commands and parameters such as `--comment`.

You can use this panel to build commands with less typing. Click the add icon, shown as a plus sign in a circle, to add a command to the input area. Then enter any additional parameters or a comment, and press **Return** to run the command.

If the endpoint is running an older version of Elastic Agent, some response actions may not be supported, as indicated by an informational icon and tooltip. [Upgrade Elastic Agent](https://www.elastic.co/guide/en/fleet/8.19/upgrade-elastic-agent.html) on the endpoint to be able to use the latest response actions.

**Unsupported-action description:** Unsupported response actions are marked with a warning triangle. Hovering over the related indicator shows a tooltip that says **Unsupported command**.

## Response actions history

Click **Response actions history** to display a log of the response actions performed on the endpoint, such as isolating a host or terminating a process. You can filter the information displayed in this view. Refer to [*Response actions history*](https://www.elastic.co/guide/en/security/8.19/response-actions-history.html "Response actions history") for more details.

**Response actions history description:** The history view shows filters for username, action, status, type, and time range, followed by a table of actions. The table includes columns such as **Time**, **Command**, **User**, **Comments**, and **Status**. Example rows show commands such as `release`, `isolate`, and `processes` with a **Successful** status.

<!-- DCOIR_SOURCE_END {"id":"knowledge.reference.elastic_actions","sha256":"24e111e712b295e09145afe327cd63769d93d59786ccc57926a9909ba83855f1"} -->

