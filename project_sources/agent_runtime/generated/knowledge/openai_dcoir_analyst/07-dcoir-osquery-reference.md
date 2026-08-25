# Generated DCOIR Knowledge Projection

> Generated, non-canonical output. Edit the atomic files under knowledge/, then rebuild all affected targets.

- Target: openai_dcoir_analyst
- Projection group: dcoir_osquery_reference
- Purpose: OSQuery table references.
- Source count: 10

<!-- DCOIR_SOURCE_BEGIN {"bytes":21034,"git_blob_sha":"c4b7e2e5deb33d46e2d1cce3dd109389e88f12df","id":"knowledge.reference.osquery_applications","path":"knowledge/Knowledge - Reference - OSQuery Application, Package, and Extension Tables.md","sha256":"8e34b186a7e87321d456414161a4209de808b592157604917607cf806ef4aaa1"} -->
# Knowledge - Reference - OSQuery Application, Package, and Extension Tables

_Exact OSQuery application, package, browser-extension, and program-inventory reference tables._

**Summary:** This page preserves the exact OSQuery source markdown for the tables in this shard. Use it as the governed exact-name reference for table and field lookup.

---

### app_schemes

**Platforms:** MacOS

macOS application schemes and handlers (e.g., http, file, mailto).

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| scheme | TEXT | Name of the scheme/protocol |
| handler | TEXT | Application label for the handler |
| enabled | INTEGER | 1 if this handler is the OS default, else 0 |
| external | INTEGER | 1 if this handler does NOT exist on macOS by default, else 0 |
| protected | INTEGER | 1 if this handler is protected (reserved) by macOS, else 0 |

### apps

**Platforms:** MacOS

macOS applications installed in known search paths (e.g., /Applications).

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Name of the Name.app folder |
| path | TEXT | Absolute and full Name.app path |
| bundle_executable | TEXT | Info properties CFBundleExecutable label |
| bundle_identifier | TEXT | Info properties CFBundleIdentifier label |
| bundle_name | TEXT | Info properties CFBundleName label |
| bundle_short_version | TEXT | Info properties CFBundleShortVersionString label |
| bundle_version | TEXT | Info properties CFBundleVersion label |
| bundle_package_type | TEXT | Info properties CFBundlePackageType label |
| environment | TEXT | Application-set environment variables |
| element | TEXT | Does the app identify as a background agent |
| compiler | TEXT | Info properties DTCompiler label |
| development_region | TEXT | Info properties CFBundleDevelopmentRegion label |
| display_name | TEXT | Info properties CFBundleDisplayName label |
| info_string | TEXT | Info properties CFBundleGetInfoString label |
| minimum_system_version | TEXT | Minimum version of macOS required for the app to run |
| category | TEXT | The UTI that categorizes the app for the App Store |
| applescript_enabled | TEXT | Info properties NSAppleScriptEnabled label |
| copyright | TEXT | Info properties NSHumanReadableCopyright label |
| last_opened_time | DOUBLE | The time that the app was last used |

### apt_sources

**Platforms:** Linux

Current list of APT repositories or software channels.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Repository name |
| source | TEXT | Source file |
| base_uri | TEXT | Repository base URI |
| release | TEXT | Release name |
| version | TEXT | Repository source version |
| maintainer | TEXT | Repository maintainer |
| components | TEXT | Repository components |
| architectures | TEXT | Repository architectures |
| pid_with_namespace | INTEGER | Pids that contain a namespace |

### chocolatey_packages

**Platforms:** Windows

Chocolatey packages installed in a system.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Package display name |
| version | TEXT | Package-supplied version |
| summary | TEXT | Package-supplied summary |
| author | TEXT | Optional package author |
| license | TEXT | License under which package is launched |
| path | TEXT | Path at which this package resides |

### chrome_extensions

**Platforms:** MacOS Linux Windows

Chrome-based browser extensions.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| browser_type | TEXT | The browser type (Valid values: chrome, chromium, opera, yandex, brave, edge, edge_beta) |
| uid | BIGINT | The local user that owns the extension |
| name | TEXT | Extension display name |
| profile | TEXT | The name of the Chrome profile that contains this extension |
| profile_path | TEXT | The profile path |
| referenced_identifier | TEXT | Extension identifier, as specified by the preferences file. Empty if the extension is not in the profile. |
| identifier | TEXT | Extension identifier, computed from its manifest. Empty in case of error. |
| version | TEXT | Extension-supplied version |
| description | TEXT | Extension-optional description |
| default_locale | TEXT | Default locale supported by extension |
| current_locale | TEXT | Current locale supported by extension |
| update_url | TEXT | Extension-supplied update URI |
| author | TEXT | Optional extension author |
| persistent | INTEGER | 1 If extension is persistent across all tabs else 0 |
| path | TEXT | Path to extension folder |
| permissions | TEXT | The permissions required by the extension |
| permissions_json | TEXT | The JSON-encoded permissions required by the extension |
| optional_permissions | TEXT | The permissions optionally required by the extensions |
| optional_permissions_json | TEXT | The JSON-encoded permissions optionally required by the extensions |
| manifest_hash | TEXT | The SHA256 hash of the manifest.json file |
| referenced | BIGINT | 1 if this extension is referenced by the Preferences file of the profile |
| from_webstore | TEXT | True if this extension was installed from the web store |
| state | TEXT | 1 if this extension is enabled |
| install_time | TEXT | Extension install time, in its original Webkit format |
| install_timestamp | BIGINT | Extension install time, converted to unix time |
| manifest_json | TEXT | The manifest file of the extension |
| key | TEXT | The extension key, from the manifest file |

### cups_destinations

**Platforms:** MacOS

Returns all configured printers.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Name of the printer |
| option_name | TEXT | Option name |
| option_value | TEXT | Option value |

### cups_jobs

**Platforms:** MacOS

Returns all completed print jobs from cups.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| title | TEXT | Title of the printed job |
| destination | TEXT | The printer the job was sent to |
| user | TEXT | The user who printed the job |
| format | TEXT | The format of the print job |
| size | INTEGER | The size of the print job |
| completed_time | INTEGER | When the job completed printing |
| processing_time | INTEGER | How long the job took to process |
| creation_time | INTEGER | When the print request was initiated |

### deb_packages

**Platforms:** Linux

The installed DEB package database.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Package name |
| version | TEXT | Package version |
| source | TEXT | Package source |
| size | BIGINT | Package size in bytes |
| arch | TEXT | Package architecture |
| revision | TEXT | Package revision |
| status | TEXT | Package status |
| maintainer | TEXT | Package maintainer |
| section | TEXT | Package section |
| priority | TEXT | Package priority |
| admindir | TEXT | libdpkg admindir. Defaults to /var/lib/dpkg |
| pid_with_namespace | INTEGER | Pids that contain a namespace |
| mount_namespace_id | TEXT | Mount namespace id |

### firefox_addons

**Platforms:** MacOS Linux Windows

Firefox browser extensions, webapps, and addons.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| uid | BIGINT | The local user that owns the addon |
| name | TEXT | Addon display name |
| identifier | TEXT | Addon identifier |
| creator | TEXT | Addon-supported creator string |
| type | TEXT | Extension, addon, webapp |
| version | TEXT | Addon-supplied version string |
| description | TEXT | Addon-supplied description string |
| source_url | TEXT | URL that installed the addon |
| visible | INTEGER | 1 If the addon is shown in browser else 0 |
| active | INTEGER | 1 If the addon is active else 0 |
| disabled | INTEGER | 1 If the addon is application-disabled else 0 |
| autoupdate | INTEGER | 1 If the addon applies background updates else 0 |
| location | TEXT | Global, profile location |
| path | TEXT | Path to plugin bundle |

### homebrew_packages

**Platforms:** MacOS

The installed homebrew package database.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Package name |
| path | TEXT | Package install path |
| version | TEXT | Current 'linked' version |
| type | TEXT | Package type ('formula' or 'cask') |
| auto_updates | INTEGER | 1 if the cask auto-updates otherwise 0 |
| app_name | TEXT | Name of the installed App (for Casks) |
| prefix | TEXT | Homebrew install prefix |

### ie_extensions

**Platforms:** Windows

Internet Explorer browser extensions.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Extension display name |
| registry_path | TEXT | Extension identifier |
| version | TEXT | Version of the executable |
| path | TEXT | Path to executable |

### jetbrains_plugins

**Platforms:** MacOS Linux Windows

JetBrains IDEs plugins.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| product_type | TEXT | The product type (Valid values: CLion, DataGrip, GoLand, IntelliJIdea, IntelliJIdeaCommunityEdition, PhpStorm, PyCharm, PyCharmCommunityEdition, ReSharper, Rider, RubyMine, RustRover, WebStorm) |
| uid | BIGINT | The local user that owns the plugin |
| name | TEXT | Name of the plugin (Title Case) |
| version | TEXT | Version of the plugin |
| vendor | TEXT | The vendor name or organization id that authored the plugin |
| path | TEXT | The path on the filesystem for the plugin. This may be a folder or a jar filename |

### npm_packages

**Platforms:** MacOS Linux Windows

Node packages installed in a system.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Package display name |
| version | TEXT | Package-supplied version |
| description | TEXT | Package-supplied description |
| author | TEXT | Package-supplied author |
| license | TEXT | License under which package is launched |
| homepage | TEXT | Package supplied homepage |
| path | TEXT | Path at which this module resides |
| directory | TEXT | Directory where node_modules are located |
| depth | INTEGER | Nesting depth of the package (0 = direct dependency) |
| max_depth | INTEGER | Maximum depth to search for nested packages (default 100, -1 = unlimited) |
| pid_with_namespace | INTEGER | Pids that contain a namespace |
| mount_namespace_id | TEXT | Mount namespace id |

### package_receipts

**Platforms:** MacOS

macOS package receipt details.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| package_id | TEXT | Package domain identifier |
| package_filename | TEXT | Filename of original .pkg file |
| version | TEXT | Installed package version |
| location | TEXT | Optional relative install path on volume |
| install_time | DOUBLE | Timestamp of install time |
| installer_name | TEXT | Name of installer process |
| path | TEXT | Path of receipt plist |

### patches

**Platforms:** Windows

Lists all the patches applied. Note: This does not include patches applied via MSI or downloaded from Windows Update (e.g. Service Packs).

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| csname | TEXT | The name of the host the patch is installed on. |
| hotfix_id | TEXT | The KB ID of the patch. |
| caption | TEXT | Short description of the patch. |
| description | TEXT | Fuller description of the patch. |
| fix_comments | TEXT | Additional comments about the patch. |
| installed_by | TEXT | The system context in which the patch as installed. |
| install_date | TEXT | Indicates when the patch was installed. Lack of a value does not indicate that the patch was not installed. |
| installed_on | TEXT | The date when the patch was installed. |

### portage_keywords

**Platforms:** Linux

A summary about portage configurations like keywords, mask and unmask.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| package | TEXT | Package name |
| version | TEXT | The version which are affected by the use flags, empty means all |
| keyword | TEXT | The keyword applied to the package |
| mask | INTEGER | If the package is masked |
| unmask | INTEGER | If the package is unmasked |

### portage_packages

**Platforms:** Linux

List of currently installed packages.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| package | TEXT | Package name |
| version | TEXT | The version which are affected by the use flags, empty means all |
| slot | TEXT | The slot used by package |
| build_time | BIGINT | Unix time when package was built |
| repository | TEXT | From which repository the ebuild was used |
| eapi | BIGINT | The eapi for the ebuild |
| size | BIGINT | The size of the package |
| world | INTEGER | If package is in the world file |

### portage_use

**Platforms:** Linux

List of enabled portage USE values for specific package.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| package | TEXT | Package name |
| version | TEXT | The version of the installed package |
| use | TEXT | USE flag which has been enabled for package |

### programs

**Platforms:** Windows

Represents products as they are installed by Windows Installer. A product generally correlates to one installation package on Windows. Some fields may be blank as Windows installation details are left to the discretion of the product author.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Commonly used product name. |
| version | TEXT | Product version information. |
| install_location | TEXT | The installation location directory of the product. |
| install_source | TEXT | The installation source of the product. |
| language | TEXT | The language of the product. |
| publisher | TEXT | Name of the product supplier. |
| uninstall_string | TEXT | Path and filename of the uninstaller. |
| install_date | TEXT | Date that this product was installed on the system. |
| identifying_number | TEXT | Product identification such as a serial number on software, or a die number on a hardware chip. |
| package_family_name | TEXT | A combination of PackageName and PublisherHash that is used to uniquely identify applications across versions and architectures. |
| upgrade_code | TEXT | Specific to MSI applications, a GUID used to identify a product suite across multiple versions. |

### python_packages

**Platforms:** MacOS Linux Windows

Python packages installed in a system. NOTE: when querying on windows, even without a users cross join, all user installed python packages will be returned. This special behavior is to not break original functionality.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Package display name |
| uid | BIGINT | The local user that owns the python package |
| version | TEXT | Package-supplied version |
| summary | TEXT | Package-supplied summary |
| author | TEXT | Optional package author |
| license | TEXT | License under which package is launched |
| path | TEXT | Path at which this module resides |
| directory | TEXT | Directory where Python modules are located |
| pid_with_namespace | INTEGER | Pids that contain a namespace |

### rpm_packages

**Platforms:** Linux

RPM packages that are currently installed on the host system.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | RPM package name |
| version | TEXT | Package version |
| release | TEXT | Package release |
| source | TEXT | Source RPM package name (optional) |
| size | BIGINT | Package size in bytes |
| sha1 | TEXT | SHA1 hash of the package contents |
| arch | TEXT | Architecture(s) supported |
| epoch | INTEGER | Package epoch value |
| install_time | INTEGER | When the package was installed |
| vendor | TEXT | Package vendor |
| package_group | TEXT | Package group |
| pid_with_namespace | INTEGER | Pids that contain a namespace |
| mount_namespace_id | TEXT | Mount namespace id |

### running_apps

**Platforms:** MacOS

macOS applications currently running on the host system.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| pid | INTEGER | The pid of the application |
| bundle_identifier | TEXT | The bundle identifier of the application |
| is_active | INTEGER | (DEPRECATED) |

### safari_extensions

**Platforms:** MacOS

Safari browser extension details for all users. This table requires Full Disk Access (FDA) permission.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| uid | BIGINT | The local user that owns the extension |
| name | TEXT | Extension display name |
| identifier | TEXT | Extension identifier |
| version | TEXT | Extension long version |
| sdk | TEXT | Bundle SDK used to compile extension |
| description | TEXT | Optional extension description text |
| path | TEXT | Path to the Info.plist describing the extension |
| bundle_version | TEXT | The version of the build that identifies an iteration of the bundle |
| copyright | TEXT | A human-readable copyright notice for the bundle |

### vscode_extensions

**Platforms:** MacOS Linux Windows

Lists all vscode extensions.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Extension Name |
| uuid | TEXT | Extension UUID |
| version | TEXT | Extension version |
| path | TEXT | Extension path |
| publisher | TEXT | Publisher Name |
| publisher_id | TEXT | Publisher ID |
| installed_at | BIGINT | Installed Timestamp |
| prerelease | INTEGER | Pre release version |
| uid | BIGINT | The local user that owns the plugin |
| vscode_edition | TEXT | The VSCode edition (vscode, vscode_insiders, vscodium, vscodium_insiders, cursor, windsurf, trae) |

### windows_optional_features

**Platforms:** Windows

Lists names and installation states of windows features. Maps to Win32_OptionalFeature WMI class.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Name of the feature |
| caption | TEXT | Caption of feature in settings UI |
| state | INTEGER | Installation state value. 1 == Enabled, 2 == Disabled, 3 == Absent |
| statename | TEXT | Installation state name. 'Enabled','Disabled','Absent' |

### windows_search

**Platforms:** Windows

Run searches against the Windows system index database using Advanced Query Syntax. See https://learn.microsoft.com/en-us/windows/win32/search/-search-3x-advancedquerysyntax for details.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | The name of the item |
| path | TEXT | The full path of the item. |
| size | BIGINT | The item size in bytes. |
| date_created | INTEGER | The unix timestamp of when the item was created. |
| date_modified | INTEGER | The unix timestamp of when the item was last modified |
| owner | TEXT | The owner of the item |
| type | TEXT | The item type |
| properties | TEXT | Additional property values JSON |
| query | TEXT | Windows search query |
| sort | TEXT | Sort for windows api |
| max_results | INTEGER | Maximum number of results returned by windows api, set to -1 for unlimited |
| additional_properties | TEXT | Comma separated list of columns to include in properties JSON |

### windows_update_history

**Platforms:** Windows

Provides the history of the windows update events.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| client_app_id | TEXT | Identifier of the client application that processed an update |
| date | BIGINT | Date and the time an update was applied |
| description | TEXT | Description of an update |
| hresult | BIGINT | HRESULT value that is returned from the operation on an update |
| operation | TEXT | Operation on an update |
| result_code | TEXT | Result of an operation on an update |
| server_selection | TEXT | Value that indicates which server provided an update |
| service_id | TEXT | Service identifier of an update service that is not a Windows update |
| support_url | TEXT | Hyperlink to the language-specific support information for an update |
| title | TEXT | Title of an update |
| update_id | TEXT | Revision-independent identifier of an update |
| update_revision | BIGINT | Revision number of an update |

### yum_sources

**Platforms:** Linux

Current list of Yum repositories or software channels.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Repository name |
| source | TEXT | Source file |
| baseurl | TEXT | Repository base URL |
| mirrorlist | TEXT | Mirrorlist URL |
| metalink | TEXT | Metalink URL |
| enabled | TEXT | Whether the repository is used |
| gpgcheck | TEXT | Whether packages are GPG checked |
| gpgkey | TEXT | URL to GPG key |
| pid_with_namespace | INTEGER | Pids that contain a namespace |

<!-- DCOIR_SOURCE_END {"id":"knowledge.reference.osquery_applications","sha256":"8e34b186a7e87321d456414161a4209de808b592157604917607cf806ef4aaa1"} -->

<!-- DCOIR_SOURCE_BEGIN {"bytes":22761,"git_blob_sha":"41141984badf6a4c448d9261c6b447b00a6c8ad0","id":"knowledge.reference.osquery_files","path":"knowledge/Knowledge - Reference - OSQuery File and Filesystem Tables.md","sha256":"b6741fe5b2e0aa2e46c7283cda7cacccbb60e7d1241d23e2f41c3b9a70de52f4"} -->
# Knowledge - Reference - OSQuery File and Filesystem Tables

_Exact OSQuery file, hash, filesystem, mount, and file-event reference tables._

**Summary:** This page preserves the exact OSQuery source markdown for the tables in this shard. Use it as the governed exact-name reference for table and field lookup.

---

### block_devices

**Platforms:** MacOS Linux

Block (buffered access) device file nodes: disks, ramdisks, and DMG containers.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Block device name |
| parent | TEXT | Block device parent name |
| vendor | TEXT | Block device vendor string |
| model | TEXT | Block device model string identifier |
| serial | TEXT | Disk serial number |
| size | BIGINT | Block device size in blocks |
| block_size | INTEGER | Block size in bytes |
| uuid | TEXT | Block device Universally Unique Identifier |
| type | TEXT | Block device type string |
| label | TEXT | Block device label string |

### deb_package_files

**Platforms:** Linux

Installed files from DEB packages that are currently installed on the system.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| package | TEXT | DEB package name |
| path | TEXT | File path within the package |
| admindir | TEXT | libdpkg admindir. Defaults to /var/lib/dpkg |

### device_file

**Platforms:** MacOS Linux

Similar to the file table, but use TSK and allow block address access.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| device | TEXT | Absolute file path to device node Required in WHERE clause |
| partition | TEXT | A partition number Required in WHERE clause |
| path | TEXT | A logical path within the device node |
| filename | TEXT | Name portion of file path |
| inode | BIGINT | Filesystem inode number |
| uid | BIGINT | Owning user ID |
| gid | BIGINT | Owning group ID |
| mode | TEXT | Permission bits |
| size | BIGINT | Size of file in bytes |
| block_size | INTEGER | Block size of filesystem |
| atime | BIGINT | Last access time |
| mtime | BIGINT | Last modification time |
| ctime | BIGINT | Creation time |
| hard_links | INTEGER | Number of hard links |
| type | TEXT | File status |

### device_hash

**Platforms:** MacOS Linux

Similar to the hash table, but use TSK and allow block address access.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| device | TEXT | Absolute file path to device node Required in WHERE clause |
| partition | TEXT | A partition number Required in WHERE clause |
| inode | BIGINT | Filesystem inode number Required in WHERE clause |
| md5 | TEXT | MD5 hash of provided inode data |
| sha1 | TEXT | SHA1 hash of provided inode data |
| sha256 | TEXT | SHA256 hash of provided inode data |

### device_partitions

**Platforms:** MacOS Linux

Use TSK to enumerate details about partitions on a disk device.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| device | TEXT | Absolute file path to device node Required in WHERE clause |
| partition | INTEGER | A partition number or description |
| label | TEXT | The partition name as stored in the partition table |
| type | TEXT | Filesystem type if recognized, otherwise, 'meta', 'normal', or 'unallocated' |
| offset | BIGINT | Byte offset from the start of the volume |
| blocks_size | BIGINT | Byte size of each block |
| blocks | BIGINT | Number of blocks |
| inodes | BIGINT | Number of meta nodes |
| flags | INTEGER | Value that describes the partition (TSK_VS_PART_FLAG_ENUM) |

### deviceguard_status

**Platforms:** Windows

Retrieve DeviceGuard info of the machine.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| version | TEXT | The version number of the Device Guard build. |
| instance_identifier | TEXT | The instance ID of Device Guard. |
| vbs_status | TEXT | The status of the virtualization based security settings. Returns UNKNOWN if an error is encountered. |
| code_integrity_policy_enforcement_status | TEXT | The status of the code integrity policy enforcement settings. Returns UNKNOWN if an error is encountered. |
| configured_security_services | TEXT | The list of configured Device Guard services. Returns UNKNOWN if an error is encountered. |
| running_security_services | TEXT | The list of running Device Guard services. Returns UNKNOWN if an error is encountered. |
| umci_policy_status | TEXT | The status of the User Mode Code Integrity security settings. Returns UNKNOWN if an error is encountered. |

### disk_events

**Platforms:** MacOS

**Table Type:** EVENTED TABLE

Track DMG disk image events (appearance/disappearance) when opened.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| action | TEXT | Appear or disappear |
| path | TEXT | Path of the DMG file accessed |
| name | TEXT | Disk event name |
| device | TEXT | Disk event BSD name |
| uuid | TEXT | UUID of the volume inside DMG if available |
| size | BIGINT | Size of partition in bytes |
| ejectable | INTEGER | 1 if ejectable, 0 if not |
| mountable | INTEGER | 1 if mountable, 0 if not |
| writable | INTEGER | 1 if writable, 0 if not |
| content | TEXT | Disk event content |
| media_name | TEXT | Disk event media name string |
| vendor | TEXT | Disk event vendor string |
| filesystem | TEXT | Filesystem if available |
| checksum | TEXT | UDIF Master checksum if available (CRC32) |
| time | BIGINT | Time of appearance/disappearance in UNIX time |
| eid | TEXT | Event ID |

### disk_info

**Platforms:** Windows

Retrieve basic information about the physical disks of a system.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| partitions | INTEGER | Number of detected partitions on disk. |
| disk_index | INTEGER | Physical drive number of the disk. |
| type | TEXT | The interface type of the disk. |
| id | TEXT | The unique identifier of the drive on the system. |
| pnp_device_id | TEXT | The unique identifier of the drive on the system. |
| disk_size | BIGINT | Size of the disk. |
| manufacturer | TEXT | The manufacturer of the disk. |
| hardware_model | TEXT | Hard drive model. |
| name | TEXT | The label of the disk object. |
| serial | TEXT | The serial number of the disk. |
| description | TEXT | The OS's description of the disk. |

### extended_attributes

**Platforms:** MacOS Linux

Returns the extended attributes for files (similar to Windows ADS).

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| path | TEXT | Absolute file path Required in WHERE clause |
| directory | TEXT | Directory of file(s) Required in WHERE clause |
| key | TEXT | Name of the value generated from the extended attribute |
| value | TEXT | The parsed information from the attribute |
| base64 | INTEGER | 1 if the value is base64 encoded else 0 |

### file

**Platforms:** MacOS Linux Windows

Interactive filesystem attributes and metadata.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| path | TEXT | Absolute file path Required in WHERE clause |
| directory | TEXT | Directory of file(s) Required in WHERE clause |
| filename | TEXT | Name portion of file path |
| inode | BIGINT | Filesystem inode number |
| uid | BIGINT | Owning user ID |
| gid | BIGINT | Owning group ID |
| mode | TEXT | Permission bits |
| device | BIGINT | Device ID (optional) |
| size | BIGINT | Size of file in bytes |
| block_size | INTEGER | Block size of filesystem |
| atime | BIGINT | Last access time |
| mtime | BIGINT | Last modification time |
| ctime | BIGINT | Last status change time |
| btime | BIGINT | (B)irth or (cr)eate time |
| hard_links | INTEGER | Number of hard links |
| symlink | INTEGER | 1 if the path is a symlink, otherwise 0 |
| type | TEXT | File status |
| symlink_target_path | TEXT | Full path of the symlink target if any |
| attributes | TEXT | File attrib string. See: https://ss64.com/nt/attrib.html |
| volume_serial | TEXT | Volume serial number |
| file_id | TEXT | file ID |
| file_version | TEXT | File version |
| product_version | TEXT | File product version |
| original_filename | TEXT | (Executable files only) Original filename |
| shortcut_target_path | TEXT | Full path to the file the shortcut points to |
| shortcut_target_type | TEXT | Display name for the target type |
| shortcut_target_location | TEXT | Folder name where the shortcut target resides |
| shortcut_start_in | TEXT | Full path to the working directory to use when executing the shortcut target |
| shortcut_run | TEXT | Window mode the target of the shortcut should be run in |
| shortcut_comment | TEXT | Comment on the shortcut |
| bsd_flags | TEXT | The BSD file flags (chflags). Possible values: NODUMP, UF_IMMUTABLE, UF_APPEND, OPAQUE, HIDDEN, ARCHIVED, SF_IMMUTABLE, SF_APPEND |
| pid_with_namespace | INTEGER | Pids that contain a namespace |
| mount_namespace_id | TEXT | Mount namespace id |

### hash

**Platforms:** MacOS Linux Windows

Filesystem hash data.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| path | TEXT | Must provide a path or directory Required in WHERE clause |
| directory | TEXT | Must provide a path or directory Required in WHERE clause |
| md5 | TEXT | MD5 hash of provided filesystem data |
| sha1 | TEXT | SHA1 hash of provided filesystem data |
| sha256 | TEXT | SHA256 hash of provided filesystem data |
| pid_with_namespace | INTEGER | Pids that contain a namespace |
| mount_namespace_id | TEXT | Mount namespace id |

### magic

**Platforms:** MacOS Linux

Magic number recognition library table.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| path | TEXT | Absolute path to target file Required in WHERE clause |
| magic_db_files | TEXT | Colon(:) separated list of files where the magic db file can be found. By default one of the following is used: /usr/share/file/magic/magic, /usr/share/misc/magic or /usr/share/misc/magic.mgc |
| data | TEXT | Magic number data from libmagic |
| mime_type | TEXT | MIME type data from libmagic |
| mime_encoding | TEXT | MIME encoding data from libmagic |

### md_devices

**Platforms:** Linux

Software RAID array settings.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| device_name | TEXT | md device name |
| status | TEXT | Current state of the array |
| raid_level | INTEGER | Current raid level of the array |
| size | BIGINT | size of the array in blocks |
| chunk_size | BIGINT | chunk size in bytes |
| raid_disks | INTEGER | Number of configured RAID disks in array |
| nr_raid_disks | INTEGER | Number of partitions or disk devices to comprise the array |
| working_disks | INTEGER | Number of working disks in array |
| active_disks | INTEGER | Number of active disks in array |
| failed_disks | INTEGER | Number of failed disks in array |
| spare_disks | INTEGER | Number of idle disks in array |
| superblock_state | TEXT | State of the superblock |
| superblock_version | TEXT | Version of the superblock |
| superblock_update_time | BIGINT | Unix timestamp of last update |
| bitmap_on_mem | TEXT | Pages allocated in in-memory bitmap, if enabled |
| bitmap_chunk_size | TEXT | Bitmap chunk size |
| bitmap_external_file | TEXT | External referenced bitmap file |
| recovery_progress | TEXT | Progress of the recovery activity |
| recovery_finish | TEXT | Estimated duration of recovery activity |
| recovery_speed | TEXT | Speed of recovery activity |
| resync_progress | TEXT | Progress of the resync activity |
| resync_finish | TEXT | Estimated duration of resync activity |
| resync_speed | TEXT | Speed of resync activity |
| reshape_progress | TEXT | Progress of the reshape activity |
| reshape_finish | TEXT | Estimated duration of reshape activity |
| reshape_speed | TEXT | Speed of reshape activity |
| check_array_progress | TEXT | Progress of the check array activity |
| check_array_finish | TEXT | Estimated duration of the check array activity |
| check_array_speed | TEXT | Speed of the check array activity |
| unused_devices | TEXT | Unused devices |
| other | TEXT | Other information associated with array from /proc/mdstat |

### md_drives

**Platforms:** Linux

Drive devices used for Software RAID.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| md_device_name | TEXT | md device name |
| drive_name | TEXT | Drive device name |
| slot | INTEGER | Slot position of disk |
| state | TEXT | State of the drive |

### md_personalities

**Platforms:** Linux

Software RAID setting supported by the kernel.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Name of personality supported by kernel |

### mdfind

**Platforms:** MacOS

Run searches against the spotlight database.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| path | TEXT | Path of the file returned from spotlight |
| query | TEXT | The query that was run to find the file Required in WHERE clause |

### mdls

**Platforms:** MacOS

Query file metadata in the Spotlight database.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| path | TEXT | Path of the file Required in WHERE clause |
| key | TEXT | Name of the metadata key |
| value | TEXT | Value stored in the metadata key |
| valuetype | TEXT | CoreFoundation type of data stored in value |

### mounts

**Platforms:** MacOS Linux

System mounted devices and filesystems (not process specific).

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| device | TEXT | Mounted device |
| device_alias | TEXT | Mounted device alias |
| path | TEXT | Mounted device path |
| type | TEXT | Mounted device type |
| blocks_size | BIGINT | Block size in bytes |
| blocks | BIGINT | Mounted device used blocks |
| blocks_free | BIGINT | Mounted device blocks available to root users, a superset of blocks_available |
| blocks_available | BIGINT | Mounted device blocks available to non-root users |
| inodes | BIGINT | Mounted device used inodes |
| inodes_free | BIGINT | Mounted device free inodes |
| flags | TEXT | Mounted device flags |

### nfs_shares

**Platforms:** MacOS

NFS shares exported by the host.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| share | TEXT | Filesystem path to the share |
| options | TEXT | Options string set on the export share |
| readonly | INTEGER | 1 if the share is exported readonly else 0 |

### ntfs_acl_permissions

**Platforms:** Windows

Retrieve NTFS ACL permission information for files and directories.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| path | TEXT | Path to the file or directory. Required in WHERE clause |
| type | TEXT | Type of access mode for the access control entry. |
| principal | TEXT | User or group to which the ACE applies. |
| access | TEXT | Specific permissions that indicate the rights described by the ACE. |
| inherited_from | TEXT | The inheritance policy of the ACE. |

### ntfs_journal_events

**Platforms:** Windows

**Table Type:** EVENTED TABLE

Track time/action changes to files specified in configuration data.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| action | TEXT | Change action (Write, Delete, etc) |
| category | TEXT | The category that the event originated from |
| old_path | TEXT | Old path (renames only) |
| path | TEXT | Path |
| record_timestamp | TEXT | Journal record timestamp |
| record_usn | TEXT | The update sequence number that identifies the journal record |
| node_ref_number | TEXT | The ordinal that associates a journal record with a filename |
| parent_ref_number | TEXT | The ordinal that associates a journal record with a filename's parent directory |
| drive_letter | TEXT | The drive letter identifying the source journal |
| file_attributes | TEXT | File attributes |
| partial | BIGINT | Set to 1 if either path or old_path only contains the file or folder name |
| time | BIGINT | Time of file event |
| eid | TEXT | Event ID |

### package_bom

**Platforms:** MacOS

macOS package bill of materials (BOM) file list.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| filepath | TEXT | Package file or directory |
| uid | INTEGER | Expected user of file or directory |
| gid | INTEGER | Expected group of file or directory |
| mode | INTEGER | Expected permissions |
| size | BIGINT | Expected file size |
| modified_time | INTEGER | Timestamp the file was installed |
| path | TEXT | Path of package bom Required in WHERE clause |

### package_install_history

**Platforms:** MacOS

macOS package install history.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| package_id | TEXT | Label packageIdentifiers |
| time | INTEGER | Label date as UNIX timestamp |
| name | TEXT | Package display name |
| version | TEXT | Package display version |
| source | TEXT | Install source: usually the installer process name |
| content_type | TEXT | Package content_type (optional) |

### plist

**Platforms:** MacOS

Read and parse a plist file.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| key | TEXT | Preference top-level key |
| subkey | TEXT | Intermediate key path, includes lists/dicts |
| value | TEXT | String value of most CF types |
| path | TEXT | (required) read preferences from a plist Required in WHERE clause |

### quicklook_cache

**Platforms:** MacOS

Files and thumbnails within macOS's Quicklook Cache.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| path | TEXT | Path of file |
| rowid | INTEGER | Quicklook file rowid key |
| fs_id | TEXT | Quicklook file fs_id key |
| volume_id | INTEGER | Parsed volume ID from fs_id |
| inode | INTEGER | Parsed file ID (inode) from fs_id |
| mtime | INTEGER | Parsed version date field |
| size | BIGINT | Parsed version size field |
| label | TEXT | Parsed version 'gen' field |
| last_hit_date | INTEGER | Apple date format for last thumbnail cache hit |
| hit_count | TEXT | Number of cache hits on thumbnail |
| icon_mode | BIGINT | Thumbnail icon mode |
| cache_path | TEXT | Path to cache data |

### recent_files

**Platforms:** Windows

Recently files (as displayed in Start Menu or File Explorer).

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| uid | BIGINT | The local user ID |
| filename | TEXT | The name of the file |
| path | TEXT | The full path of the file |
| type | TEXT | Display type for the file |
| mtime | BIGINT | Last modification time of the shortcut (usually corresponds to last opened time for the file) |
| shortcut_path | TEXT | Path to the shortcut where Windows stores the recent file data |

### rpm_package_files

**Platforms:** Linux

Installed files from RPM packages that are currently installed on the system.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| package | TEXT | RPM package name |
| path | TEXT | File path within the package |
| username | TEXT | File default username from info DB |
| groupname | TEXT | File default groupname from info DB |
| mode | TEXT | File permissions mode from info DB |
| size | BIGINT | Expected file size in bytes from RPM info DB |
| sha256 | TEXT | SHA256 file digest from RPM info DB |

### shared_memory

**Platforms:** Linux

OS shared memory regions.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| shmid | INTEGER | Shared memory segment ID |
| owner_uid | BIGINT | User ID of owning process |
| creator_uid | BIGINT | User ID of creator process |
| pid | BIGINT | Process ID to last use the segment |
| creator_pid | BIGINT | Process ID that created the segment |
| atime | BIGINT | Attached time |
| dtime | BIGINT | Detached time |
| ctime | BIGINT | Changed time |
| permissions | TEXT | Memory segment permissions |
| size | BIGINT | Size in bytes |
| attached | INTEGER | Number of attached processes |
| status | TEXT | Destination/attach status |
| locked | INTEGER | 1 if segment is locked else 0 |

### shared_resources

**Platforms:** Windows

Displays shared resources on a computer system running Windows. This may be a disk drive, printer, interprocess communication, or other sharable device.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| description | TEXT | A textual description of the object |
| install_date | TEXT | Indicates when the object was installed. Lack of a value does not indicate that the object is not installed. |
| status | TEXT | String that indicates the current status of the object. |
| allow_maximum | INTEGER | Number of concurrent users for this resource has been limited. If True, the value in the MaximumAllowed property is ignored. |
| maximum_allowed | BIGINT | Limit on the maximum number of users allowed to use this resource concurrently. The value is only valid if the AllowMaximum property is set to FALSE. |
| name | TEXT | Alias given to a path set up as a share on a computer system running Windows. |
| path | TEXT | Local path of the Windows share. |
| type | BIGINT | Type of resource being shared. Types include: disk drives, print queues, interprocess communications (IPC), and general devices. |
| type_name | TEXT | Human readable value for the 'type' column |

### smbios_tables

**Platforms:** MacOS Linux

BIOS (DMI) structure common details and content.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| number | INTEGER | Table entry number |
| type | INTEGER | Table entry type |
| description | TEXT | Table entry description |
| handle | INTEGER | Table entry handle |
| header_size | INTEGER | Header size in bytes |
| size | INTEGER | Table entry size in bytes |
| md5 | TEXT | MD5 hash of table entry |

### yara_file

**Platforms:** MacOS Linux Windows

**Status:** New

Triggers one-off YARA query for files at the specified path. Additionally requires one of `sig_group`, `sigfile`, or `sigrule`.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| path | TEXT | The path scanned Required in WHERE clause |
| matches | TEXT | List of YARA matches |
| count | INTEGER | Number of YARA matches |
| sig_group | TEXT | Signature group used |
| sigfile | TEXT | Signature file used |
| sigrule | TEXT | Signature strings used |
| strings | TEXT | Matching strings |
| tags | TEXT | Matching tags |
| sigurl | TEXT | Signature url |
| pid_with_namespace | INTEGER | Pids that contain a namespace |

<!-- DCOIR_SOURCE_END {"id":"knowledge.reference.osquery_files","sha256":"b6741fe5b2e0aa2e46c7283cda7cacccbb60e7d1241d23e2f41c3b9a70de52f4"} -->

<!-- DCOIR_SOURCE_BEGIN {"bytes":18757,"git_blob_sha":"e511b14ea36c20e36b4c4198dae8c3f6e499957d","id":"knowledge.reference.osquery_network","path":"knowledge/Knowledge - Reference - OSQuery Network and Connection Tables.md","sha256":"f9f3d0e15c71666bd116d1d907224a22b36fafcb873543129403eae7404ad46d"} -->
# Knowledge - Reference - OSQuery Network and Connection Tables

_Exact OSQuery network, DNS, interface, route, and socket reference tables._

**Summary:** This page preserves the exact OSQuery source markdown for the tables in this shard. Use it as the governed exact-name reference for table and field lookup.

---

### arp_cache

**Platforms:** MacOS Linux Windows

Address resolution cache, both static and dynamic (from ARP, NDP).

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| address | TEXT | IPv4 address target |
| mac | TEXT | MAC address of broadcasted address |
| interface | TEXT | Interface of the network for the MAC |
| permanent | TEXT | 1 for true, 0 for false |

### connectivity

**Platforms:** Windows

Provides the overall system's network state.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| disconnected | INTEGER | True if the all interfaces are not connected to any network |
| ipv4_no_traffic | INTEGER | True if any interface is connected via IPv4, but has seen no traffic |
| ipv6_no_traffic | INTEGER | True if any interface is connected via IPv6, but has seen no traffic |
| ipv4_subnet | INTEGER | True if any interface is connected to the local subnet via IPv4 |
| ipv4_local_network | INTEGER | True if any interface is connected to a routed network via IPv4 |
| ipv4_internet | INTEGER | True if any interface is connected to the Internet via IPv4 |
| ipv6_subnet | INTEGER | True if any interface is connected to the local subnet via IPv6 |
| ipv6_local_network | INTEGER | True if any interface is connected to a routed network via IPv6 |
| ipv6_internet | INTEGER | True if any interface is connected to the Internet via IPv6 |

### curl

**Platforms:** MacOS Linux Windows

Perform an http request and return stats about it.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| url | TEXT | The url for the request Required in WHERE clause |
| method | TEXT | The HTTP method for the request |
| user_agent | TEXT | The user-agent string to use for the request |
| response_code | INTEGER | The HTTP status code for the response |
| round_trip_time | BIGINT | Time taken to complete the request |
| bytes | BIGINT | Number of bytes in the response |
| result | TEXT | The HTTP response body |

### curl_certificate

**Platforms:** MacOS Linux Windows

Inspect TLS certificates by connecting to input hostnames.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| hostname | TEXT | Hostname to CURL (domain[:port], e.g. osquery.io) Required in WHERE clause |
| common_name | TEXT | Common name of company issued to |
| organization | TEXT | Organization issued to |
| organization_unit | TEXT | Organization unit issued to |
| serial_number | TEXT | Certificate serial number |
| issuer_common_name | TEXT | Issuer common name |
| issuer_organization | TEXT | Issuer organization |
| issuer_organization_unit | TEXT | Issuer organization unit |
| valid_from | TEXT | Period of validity start date |
| valid_to | TEXT | Period of validity end date |
| sha256_fingerprint | TEXT | SHA-256 fingerprint |
| sha1_fingerprint | TEXT | SHA1 fingerprint |
| version | INTEGER | Version Number |
| signature_algorithm | TEXT | Signature Algorithm |
| signature | TEXT | Signature |
| subject_key_identifier | TEXT | Subject Key Identifier |
| authority_key_identifier | TEXT | Authority Key Identifier |
| key_usage | TEXT | Usage of key in certificate |
| extended_key_usage | TEXT | Extended usage of key in certificate |
| policies | TEXT | Certificate Policies |
| subject_alternative_names | TEXT | Subject Alternative Name |
| issuer_alternative_names | TEXT | Issuer Alternative Name |
| info_access | TEXT | Authority Information Access |
| subject_info_access | TEXT | Subject Information Access |
| policy_mappings | TEXT | Policy Mappings |
| has_expired | INTEGER | 1 if the certificate has expired, 0 otherwise |
| basic_constraint | TEXT | Basic Constraints |
| name_constraints | TEXT | Name Constraints |
| policy_constraints | TEXT | Policy Constraints |
| dump_certificate | INTEGER | Set this value to '1' to dump certificate |
| timeout | INTEGER | Set this value to the timeout in seconds to complete the TLS handshake (default 4s, use 0 for no timeout) |
| pem | TEXT | Certificate PEM format |

### dns_cache

**Platforms:** Windows

Enumerate the DNS cache using the undocumented DnsGetCacheDataTable function in dnsapi.dll.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | DNS record name |
| type | TEXT | DNS record type |
| flags | INTEGER | DNS record flags |

### dns_lookup_events

**Platforms:** Windows

**Table Type:** EVENTED TABLE

DNS lookups performed through the Windows DNS stack.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| eid | INTEGER | Event ID |
| time | BIGINT | Event timestamp in Unix format |
| time_windows | BIGINT | Event timestamp in Windows format |
| datetime | TEXT | Event timestamp in DATETIME format |
| pid | BIGINT | Process ID of process making the lookup |
| path | TEXT | Path to binary of process making the lookup (sometimes unavailable for very short-lived processes) |
| username | TEXT | User rights - primary token username |
| name | TEXT | Name being queried in lookup |
| type | TEXT | DNS record type of lookup as string |
| type_id | INTEGER | Integer type ID for record type |
| status | INTEGER | Response status code |
| response | TEXT | Results returned by lookup |

### dns_resolvers

**Platforms:** MacOS Linux

Resolvers used by this host. Note: On Windows this data is available in the interface_details table.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| id | INTEGER | Address type index or order |
| type | TEXT | Address type: sortlist, nameserver, search |
| address | TEXT | Resolver IP/IPv6 address |
| netmask | TEXT | Address (sortlist) netmask length |
| options | BIGINT | Resolver options |
| pid_with_namespace | INTEGER | Pids that contain a namespace |

### etc_hosts

**Platforms:** MacOS Linux Windows

Line-parsed /etc/hosts.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| address | TEXT | IP address mapping |
| hostnames | TEXT | Raw hosts mapping |
| pid_with_namespace | INTEGER | Pids that contain a namespace |

### etc_protocols

**Platforms:** MacOS Linux Windows

Line-parsed /etc/protocols.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Protocol name |
| number | INTEGER | Protocol number |
| alias | TEXT | Protocol alias |
| comment | TEXT | Comment with protocol description |

### etc_services

**Platforms:** MacOS Linux Windows

Line-parsed /etc/services.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Service name |
| port | INTEGER | Service port number |
| protocol | TEXT | Transport protocol (TCP/UDP) |
| aliases | TEXT | Optional space separated list of other names for a service |
| comment | TEXT | Optional comment for a service. |

### interface_addresses

**Platforms:** MacOS Linux Windows

Network interfaces and relevant metadata.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| interface | TEXT | Interface name |
| address | TEXT | Specific address for interface |
| mask | TEXT | Interface netmask |
| broadcast | TEXT | Broadcast address for the interface |
| point_to_point | TEXT | PtP address for the interface |
| type | TEXT | Type of address. One of dhcp, manual, auto, other, unknown |
| friendly_name | TEXT | The friendly display name of the interface. |

### interface_details

**Platforms:** MacOS Linux Windows

Detailed information and stats of network interfaces.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| interface | TEXT | Interface name |
| mac | TEXT | MAC of interface (optional) |
| type | INTEGER | Interface type (includes virtual) |
| mtu | INTEGER | Network MTU |
| metric | INTEGER | Metric based on the speed of the interface |
| flags | INTEGER | Flags (netdevice) for the device |
| ipackets | BIGINT | Input packets |
| opackets | BIGINT | Output packets |
| ibytes | BIGINT | Input bytes |
| obytes | BIGINT | Output bytes |
| ierrors | BIGINT | Input errors |
| oerrors | BIGINT | Output errors |
| idrops | BIGINT | Input drops |
| odrops | BIGINT | Output drops |
| collisions | BIGINT | Packet Collisions detected |
| last_change | BIGINT | Time of last device modification (optional) |
| link_speed | BIGINT | Interface speed in Mb/s |
| pci_slot | TEXT | PCI slot number |
| friendly_name | TEXT | The friendly display name of the interface. |
| description | TEXT | Short description of the object a one-line string. |
| manufacturer | TEXT | Name of the network adapter's manufacturer. |
| connection_id | TEXT | Name of the network connection as it appears in the Network Connections Control Panel program. |
| connection_status | TEXT | State of the network adapter connection to the network. |
| enabled | INTEGER | Indicates whether the adapter is enabled or not. |
| physical_adapter | INTEGER | Indicates whether the adapter is a physical or a logical adapter. |
| speed | INTEGER | Estimate of the current bandwidth in bits per second. |
| service | TEXT | The name of the service the network adapter uses. |
| dhcp_enabled | INTEGER | If TRUE, the dynamic host configuration protocol (DHCP) server automatically assigns an IP address to the computer system when establishing a network connection. |
| dhcp_lease_expires | TEXT | Expiration date and time for a leased IP address that was assigned to the computer by the dynamic host configuration protocol (DHCP) server. |
| dhcp_lease_obtained | TEXT | Date and time the lease was obtained for the IP address assigned to the computer by the dynamic host configuration protocol (DHCP) server. |
| dhcp_server | TEXT | IP address of the dynamic host configuration protocol (DHCP) server. |
| dns_domain | TEXT | Organization name followed by a period and an extension that indicates the type of organization, such as 'microsoft.com'. |
| dns_domain_suffix_search_order | TEXT | Array of DNS domain suffixes to be appended to the end of host names during name resolution. |
| dns_host_name | TEXT | Host name used to identify the local computer for authentication by some utilities. |
| dns_server_search_order | TEXT | Array of server IP addresses to be used in querying for DNS servers. |

### interface_ipv6

**Platforms:** MacOS Linux

IPv6 configuration and stats of network interfaces.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| interface | TEXT | Interface name |
| hop_limit | INTEGER | Current Hop Limit |
| forwarding_enabled | INTEGER | Enable IP forwarding |
| redirect_accept | INTEGER | Accept ICMP redirect messages |
| rtadv_accept | INTEGER | Accept ICMP Router Advertisement |

### iptables

**Platforms:** Linux

Linux IP packet filtering and NAT tool.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| filter_name | TEXT | Packet matching filter table name. |
| chain | TEXT | Size of module content. |
| policy | TEXT | Policy that applies for this rule. |
| target | TEXT | Target that applies for this rule. |
| protocol | INTEGER | Protocol number identification. |
| src_port | TEXT | Protocol source port(s). |
| dst_port | TEXT | Protocol destination port(s). |
| src_ip | TEXT | Source IP address. |
| src_mask | TEXT | Source IP address mask. |
| iniface | TEXT | Input interface for the rule. |
| iniface_mask | TEXT | Input interface mask for the rule. |
| dst_ip | TEXT | Destination IP address. |
| dst_mask | TEXT | Destination IP address mask. |
| outiface | TEXT | Output interface for the rule. |
| outiface_mask | TEXT | Output interface mask for the rule. |
| match | TEXT | Matching rule that applies. |
| packets | INTEGER | Number of matching packets for this rule. |
| bytes | INTEGER | Number of matching bytes for this rule. |

### listening_ports

**Platforms:** MacOS Linux Windows

Processes with listening (bound) network sockets/ports.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| pid | INTEGER | Process (or thread) ID |
| port | INTEGER | Transport layer port |
| protocol | INTEGER | Transport protocol (TCP/UDP) |
| family | INTEGER | Network protocol (IPv4, IPv6) |
| address | TEXT | Specific address for bind |
| fd | BIGINT | Socket file descriptor number |
| socket | BIGINT | Socket handle or inode number |
| path | TEXT | Path for UNIX domain sockets |
| net_namespace | TEXT | The inode number of the network namespace |

### pipes

**Platforms:** Windows

Named and Anonymous pipes.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| pid | BIGINT | Process ID of the process to which the pipe belongs |
| name | TEXT | Name of the pipe |
| instances | INTEGER | Number of instances of the named pipe |
| max_instances | INTEGER | The maximum number of instances creatable for this pipe |
| flags | TEXT | The flags indicating whether this pipe connection is a server or client end, and if the pipe for sending messages or bytes |

### routes

**Platforms:** MacOS Linux Windows

The active route table for the host system.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| destination | TEXT | Destination IP address |
| netmask | INTEGER | Netmask length |
| gateway | TEXT | Route gateway |
| source | TEXT | Route source |
| flags | INTEGER | Flags to describe route |
| interface | TEXT | Route local interface |
| mtu | INTEGER | Maximum Transmission Unit for the route |
| metric | INTEGER | Cost of route. Lowest is preferred |
| type | TEXT | Type of route |
| hopcount | INTEGER | Max hops expected |

### socket_events

**Platforms:** MacOS Linux

**Table Type:** EVENTED TABLE

Track network socket bind, connect, and accepts.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| action | TEXT | The socket action (bind, connect, accept) |
| pid | BIGINT | Process (or thread) ID |
| path | TEXT | Path of executed file |
| fd | TEXT | The file description for the process socket |
| auid | BIGINT | Audit User ID |
| family | INTEGER | The Internet protocol family ID |
| protocol | INTEGER | The network protocol ID |
| local_address | TEXT | Local address associated with socket |
| remote_address | TEXT | Remote address associated with socket |
| local_port | INTEGER | Local network protocol port number |
| remote_port | INTEGER | Remote network protocol port number |
| socket | TEXT | The local path (UNIX domain socket only) |
| time | BIGINT | Time of execution in UNIX time |
| uptime | BIGINT | Time of execution in system uptime |
| eid | TEXT | Event ID |
| success | INTEGER | Deprecated. Use the 'status' column instead |
| status | TEXT | Either 'succeeded', 'failed', 'in_progress' (connect() on non-blocking socket) or 'no_client' (null accept() on non-blocking socket) |

### wifi_networks

**Platforms:** MacOS

macOS known/remembered Wi-Fi networks list.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| ssid | TEXT | SSID octets of the network |
| network_name | TEXT | Name of the network |
| security_type | TEXT | Type of security on this network |
| last_connected | INTEGER | Last time this network was connected to as a unix_time (max of last_connected_automatic and last_connected_manual, if available) |
| last_connected_automatic | INTEGER | Last time this network was automatically connected to by the system as a unix_time |
| last_connected_manual | INTEGER | Last time this network was manually connected to by the user as a unix_time |
| passpoint | INTEGER | 1 if Passpoint is supported, 0 otherwise |
| possibly_hidden | INTEGER | 1 if network is possibly a hidden network, 0 otherwise |
| roaming | INTEGER | 1 if roaming is supported, 0 otherwise |
| roaming_profile | TEXT | Describe the roaming profile, usually one of Single, Dual or Multi |
| auto_login | INTEGER | 1 if auto login is enabled, 0 otherwise |
| temporarily_disabled | INTEGER | 1 if this network is temporarily disabled, 0 otherwise |
| disabled | INTEGER | 1 if this network is disabled, 0 otherwise |
| add_reason | TEXT | Shows why this network was added, via menubar or command line or something else |
| added_at | INTEGER | Time this network was added as a unix_time |
| captive_portal | INTEGER | 1 if this network has a captive portal, 0 otherwise |
| captive_login_date | INTEGER | Time this network logged in to a captive portal as unix_time |
| was_captive_network | INTEGER | 1 if this network was previously a captive network, 0 otherwise |
| auto_join | INTEGER | 1 if this network set to join automatically, 0 otherwise |
| personal_hotspot | INTEGER | 1 if this network is a personal hotspot, 0 otherwise |

### wifi_status

**Platforms:** MacOS

macOS current WiFi status. This table requires Full Disk Access (FDA) permission to retrieve network_name.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| interface | TEXT | Name of the interface |
| ssid | TEXT | SSID octets of the network |
| bssid | TEXT | The current basic service set identifier |
| network_name | TEXT | Name of the network |
| country_code | TEXT | The country code (ISO/IEC 3166-1:1997) for the network |
| security_type | TEXT | Type of security on this network |
| rssi | INTEGER | The current received signal strength indication (dbm) |
| noise | INTEGER | The current noise measurement (dBm) |
| channel | INTEGER | Channel number |
| channel_width | INTEGER | Channel width |
| channel_band | INTEGER | Channel band |
| transmit_rate | TEXT | The current transmit rate |
| mode | TEXT | The current operating mode for the Wi-Fi interface |

### wifi_survey

**Platforms:** MacOS

Scan for nearby WiFi networks.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| interface | TEXT | Name of the interface |
| ssid | TEXT | SSID octets of the network |
| bssid | TEXT | The current basic service set identifier |
| network_name | TEXT | Name of the network |
| country_code | TEXT | The country code (ISO/IEC 3166-1:1997) for the network |
| rssi | INTEGER | The current received signal strength indication (dbm) |
| noise | INTEGER | The current noise measurement (dBm) |
| channel | INTEGER | Channel number |
| channel_width | INTEGER | Channel width |
| channel_band | INTEGER | Channel band |

<!-- DCOIR_SOURCE_END {"id":"knowledge.reference.osquery_network","sha256":"f9f3d0e15c71666bd116d1d907224a22b36fafcb873543129403eae7404ad46d"} -->

<!-- DCOIR_SOURCE_BEGIN {"bytes":16462,"git_blob_sha":"92790c3e5162918239a246365dfa11d96d562ff8","id":"knowledge.reference.osquery_persistence","path":"knowledge/Knowledge - Reference - OSQuery Persistence and Startup Tables.md","sha256":"75889e8e8a92c6e37df66652172b5439750911f4bcb8301545aa14fe6f189076"} -->
# Knowledge - Reference - OSQuery Persistence and Startup Tables

_Exact OSQuery persistence, startup, scheduled-task, service, and shim reference tables._

**Summary:** This page preserves the exact OSQuery source markdown for the tables in this shard. Use it as the governed exact-name reference for table and field lookup.

---

### appcompat_shims

**Platforms:** Windows

Application Compatibility shims are a way to persist malware. This table presents the AppCompat Shim information from the registry in a nice format. See http://files.brucon.org/2015/Tomczak_and_Ballenthin_Shims_for_the_Win.pdf for more details.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| executable | TEXT | Name of the executable that is being shimmed. This is pulled from the registry. |
| path | TEXT | This is the path to the SDB database. |
| description | TEXT | Description of the SDB. |
| install_time | INTEGER | Install time of the SDB |
| type | TEXT | Type of the SDB database. |
| sdb_id | TEXT | Unique GUID of the SDB. |

### autoexec

**Platforms:** Windows

Aggregate of executables that will automatically execute on the target machine. This is an amalgamation of other tables like services, scheduled_tasks, startup_items and more.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| path | TEXT | Path to the executable |
| name | TEXT | Name of the program |
| source | TEXT | Source table of the autoexec item |

### background_activities_moderator

**Platforms:** Windows

Background Activities Moderator (BAM) tracks application execution.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| path | TEXT | Application file path. |
| last_execution_time | BIGINT | Most recent time application was executed. |
| sid | TEXT | User SID. |

### browser_plugins

**Platforms:** MacOS

All C/NPAPI browser plugin details for all users. C/NPAPI has been deprecated on all major browsers. To query for plugins on modern browsers, try: `chrome_extensions` `firefox_addons` `safari_extensions`.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| uid | BIGINT | The local user that owns the plugin |
| name | TEXT | Plugin display name |
| identifier | TEXT | Plugin identifier |
| version | TEXT | Plugin short version |
| sdk | TEXT | Build SDK used to compile plugin |
| description | TEXT | Plugin description text |
| development_region | TEXT | Plugin language-localization |
| native | INTEGER | Plugin requires native execution |
| path | TEXT | Path to plugin bundle |
| disabled | INTEGER | Is the plugin disabled. 1 = Disabled |

### chrome_extension_content_scripts

**Platforms:** MacOS Linux Windows

Chrome browser extension content scripts.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| browser_type | TEXT | The browser type (Valid values: chrome, chromium, opera, yandex, brave) |
| uid | BIGINT | The local user that owns the extension |
| identifier | TEXT | Extension identifier |
| version | TEXT | Extension-supplied version |
| script | TEXT | The content script used by the extension |
| match | TEXT | The pattern that the script is matched against |
| profile_path | TEXT | The profile path |
| path | TEXT | Path to extension folder |
| referenced | BIGINT | 1 if this extension is referenced by the Preferences file of the profile |

### drivers

**Platforms:** Windows

Details for in-use Windows device drivers. This does not display installed but unused drivers.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| device_id | TEXT | Device ID |
| device_name | TEXT | Device name |
| image | TEXT | Path to driver image file |
| description | TEXT | Driver description |
| service | TEXT | Driver service name, if one exists |
| service_key | TEXT | Driver service registry key |
| version | TEXT | Driver version |
| inf | TEXT | Associated inf file |
| class | TEXT | Device/driver class name |
| provider | TEXT | Driver provider |
| manufacturer | TEXT | Device manufacturer |
| driver_key | TEXT | Driver key |
| date | BIGINT | Driver date |
| signed | INTEGER | Whether the driver is signed or not |

### event_taps

**Platforms:** MacOS

Returns information about installed event taps.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| enabled | INTEGER | Is the Event Tap enabled |
| event_tap_id | INTEGER | Unique ID for the Tap |
| event_tapped | TEXT | The mask that identifies the set of events to be observed. |
| process_being_tapped | INTEGER | The process ID of the target application |
| tapping_process | INTEGER | The process ID of the application that created the event tap. |

### kernel_extensions

**Platforms:** MacOS

macOS's kernel extensions, both loaded and within the load search path.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| idx | INTEGER | Extension load tag or index |
| refs | INTEGER | Reference count |
| size | BIGINT | Bytes of wired memory used by extension |
| name | TEXT | Extension label |
| version | TEXT | Extension version |
| linked_against | TEXT | Indexes of extensions this extension is linked against |
| path | TEXT | Optional path to extension bundle |

### kernel_modules

**Platforms:** Linux

Linux kernel modules both loaded and within the load search path.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Module name |
| size | BIGINT | Size of module content |
| used_by | TEXT | Module reverse dependencies |
| status | TEXT | Kernel module status |
| address | TEXT | Kernel module address |

### launchd

**Platforms:** MacOS

LaunchAgents and LaunchDaemons from default search paths.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| path | TEXT | Path to daemon or agent plist |
| name | TEXT | File name of plist (used by launchd) |
| label | TEXT | Daemon or agent service name |
| program | TEXT | Path to target program |
| run_at_load | TEXT | Should the program run on launch load |
| keep_alive | TEXT | Should the process be restarted if killed |
| on_demand | TEXT | Deprecated key, replaced by keep_alive |
| disabled | TEXT | Skip loading this daemon or agent on boot |
| username | TEXT | Run this daemon or agent as this username |
| groupname | TEXT | Run this daemon or agent as this group |
| stdout_path | TEXT | Pipe stdout to a target path |
| stderr_path | TEXT | Pipe stderr to a target path |
| start_interval | TEXT | Frequency to run in seconds |
| program_arguments | TEXT | Command line arguments passed to program |
| watch_paths | TEXT | Key that launches daemon or agent if path is modified |
| queue_directories | TEXT | Similar to watch_paths but only with non-empty directories |
| inetd_compatibility | TEXT | Run this daemon or agent as it was launched from inetd |
| start_on_mount | TEXT | Run daemon or agent every time a filesystem is mounted |
| root_directory | TEXT | Key used to specify a directory to chroot to before launch |
| working_directory | TEXT | Key used to specify a directory to chdir to before launch |
| process_type | TEXT | Key describes the intended purpose of the job |

### launchd_overrides

**Platforms:** MacOS

Override keys, per user, for LaunchDaemons and Agents.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| label | TEXT | Daemon or agent service name |
| key | TEXT | Name of the override key |
| value | TEXT | Overridden value |
| uid | BIGINT | User ID applied to the override, 0 applies to all |
| path | TEXT | Path to daemon or agent plist |

### scheduled_tasks

**Platforms:** Windows

Lists all of the tasks in the Windows task scheduler.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Name of the scheduled task |
| action | TEXT | Actions executed by the scheduled task |
| path | TEXT | Path to the executable to be run |
| enabled | INTEGER | Whether or not the scheduled task is enabled |
| state | TEXT | State of the scheduled task |
| hidden | INTEGER | Whether or not the task is visible in the UI |
| last_run_time | BIGINT | Timestamp the task last ran |
| next_run_time | BIGINT | Timestamp the task is scheduled to run next |
| last_run_message | TEXT | Exit status message of the last task run |
| last_run_code | TEXT | Exit status code of the last task run |

### services

**Platforms:** Windows

Lists all installed Windows services and their relevant data.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Service name |
| service_type | TEXT | Service Type: OWN_PROCESS, SHARE_PROCESS and maybe Interactive (can interact with the desktop) |
| display_name | TEXT | Service Display name |
| status | TEXT | Service Current status: STOPPED, START_PENDING, STOP_PENDING, RUNNING, CONTINUE_PENDING, PAUSE_PENDING, PAUSED |
| pid | INTEGER | the Process ID of the service |
| start_type | TEXT | Service start type: BOOT_START, SYSTEM_START, AUTO_START, DEMAND_START, DISABLED |
| win32_exit_code | INTEGER | The error code that the service uses to report an error that occurs when it is starting or stopping |
| service_exit_code | INTEGER | The service-specific error code that the service returns when an error occurs while the service is starting or stopping |
| path | TEXT | Path to Service Executable |
| module_path | TEXT | Path to ServiceDll |
| description | TEXT | Service Description |
| user_account | TEXT | The name of the account that the service process will be logged on as when it runs. This name can be of the form Domain\\UserName. If the account belongs to the built-in domain, the name can be of the form .\\UserName. |

### shimcache

**Platforms:** Windows

Application Compatibility Cache, contains artifacts of execution.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| entry | INTEGER | Execution order. |
| path | TEXT | This is the path to the executed file. |
| modified_time | INTEGER | File Modified time. |
| execution_flag | INTEGER | Boolean Execution flag, 1 for execution, 0 for no execution, -1 for missing (this flag does not exist on Windows 10 and higher). |

### startup_items

**Platforms:** MacOS Linux Windows

Applications and binaries set as startup items.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Name of startup item |
| path | TEXT | Path of startup item |
| args | TEXT | Arguments provided to startup executable |
| type | TEXT | Type of startup item. On macOS this can be app, agent (LaunchAgent), daemon (LaunchDaemon), login item, or user item. |
| source | TEXT | Directory containing startup item (on macOS, the subsystem providing it) |
| status | TEXT | Startup status. On Linux: enabled or disabled. On macOS: Combination of enabled, allowed, notified, and hidden. Apple does not seem to document these status values, but allowed seems to indicate whether it is enabled in System Settings. |
| username | TEXT | The user associated with the startup item |

### system_extensions

**Platforms:** MacOS

macOS (>= 10.15) system extension table.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| path | TEXT | Original path of system extension |
| UUID | TEXT | Extension unique id |
| state | TEXT | System extension state |
| identifier | TEXT | Identifier name |
| version | TEXT | System extension version |
| category | TEXT | System extension category |
| bundle_path | TEXT | System extension bundle path |
| team | TEXT | Signing team ID |
| mdm_managed | INTEGER | 1 if managed by MDM system extension payload configuration, 0 otherwise |

### systemd_units

**Platforms:** Linux

Track systemd units.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| id | TEXT | Unique unit identifier |
| description | TEXT | Unit description |
| load_state | TEXT | Reflects whether the unit definition was properly loaded |
| active_state | TEXT | The high-level unit activation state, i.e. generalization of SUB |
| sub_state | TEXT | The low-level unit activation state, values depend on unit type |
| unit_file_state | TEXT | Whether the unit file is enabled, e.g. `enabled`, `masked`, `disabled`, etc |
| following | TEXT | The name of another unit that this unit follows in state |
| object_path | TEXT | The object path for this unit |
| job_id | BIGINT | Next queued job id |
| job_type | TEXT | Job type |
| job_path | TEXT | The object path for the job |
| fragment_path | TEXT | The unit file path this unit was read from, if there is any |
| user | TEXT | The configured user, if any |
| source_path | TEXT | Path to the (possibly generated) unit configuration file |

### wmi_cli_event_consumers

**Platforms:** Windows

WMI CommandLineEventConsumer, which can be used for persistence on Windows. See https://www.blackhat.com/docs/us-15/materials/us-15-Graeber-Abusing-Windows-Management-Instrumentation-WMI-To-Build-A-Persistent%20Asynchronous-And-Fileless-Backdoor-wp.pdf for more details.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| namespace | TEXT | The WMI namespace where the consumer was found. |
| name | TEXT | Unique name of a consumer. |
| command_line_template | TEXT | Standard string template that specifies the process to be started. This property can be NULL, and the ExecutablePath property is used as the command line. |
| executable_path | TEXT | Module to execute. The string can specify the full path and file name of the module to execute, or it can specify a partial name. If a partial name is specified, the current drive and current directory are assumed. |
| class | TEXT | The name of the class. |
| relative_path | TEXT | Relative path to the class or instance. |

### wmi_event_filters

**Platforms:** Windows

Lists WMI event filters.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| namespace | TEXT | The WMI namespace where the filter was found. |
| name | TEXT | Unique identifier of an event filter. |
| query | TEXT | Windows Management Instrumentation Query Language (WQL) event query that specifies the set of events for consumer notification, and the specific conditions for notification. |
| query_language | TEXT | Query language that the query is written in. |
| class | TEXT | The name of the class. |
| relative_path | TEXT | Relative path to the class or instance. |

### wmi_filter_consumer_binding

**Platforms:** Windows

Lists the relationship between event consumers and filters.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| namespace | TEXT | The WMI namespace where the binding was found. |
| consumer | TEXT | Reference to an instance of __EventConsumer that represents the object path to a logical consumer, the recipient of an event. |
| filter | TEXT | Reference to an instance of __EventFilter that represents the object path to an event filter which is a query that specifies the type of event to be received. |
| class | TEXT | The name of the class. |
| relative_path | TEXT | Relative path to the class or instance. |

### wmi_script_event_consumers

**Platforms:** Windows

WMI ActiveScriptEventConsumer, which can be used for persistence on Windows. See https://www.blackhat.com/docs/us-15/materials/us-15-Graeber-Abusing-Windows-Management-Instrumentation-WMI-To-Build-A-Persistent%20Asynchronous-And-Fileless-Backdoor-wp.pdf for more details.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| namespace | TEXT | The WMI namespace where the consumer was found. |
| name | TEXT | Unique identifier for the event consumer. |
| scripting_engine | TEXT | Name of the scripting engine to use, for example, 'VBScript'. This property cannot be NULL. |
| script_file_name | TEXT | Name of the file from which the script text is read, intended as an alternative to specifying the text of the script in the ScriptText property. |
| script_text | TEXT | Text of the script that is expressed in a language known to the scripting engine. This property must be NULL if the ScriptFileName property is not NULL. |
| class | TEXT | The name of the class. |
| relative_path | TEXT | Relative path to the class or instance. |

<!-- DCOIR_SOURCE_END {"id":"knowledge.reference.osquery_persistence","sha256":"75889e8e8a92c6e37df66652172b5439750911f4bcb8301545aa14fe6f189076"} -->

<!-- DCOIR_SOURCE_BEGIN {"bytes":21362,"git_blob_sha":"18786bbeb6fbd0ae670087765cf39b6dbc4972b8","id":"knowledge.reference.osquery_process","path":"knowledge/Knowledge - Reference - OSQuery Process and Execution Tables.md","sha256":"3a13d1baff6b899a6de385f67e7f54c1efc92b60c13bb2186e5429046c138a01"} -->
# Knowledge - Reference - OSQuery Process and Execution Tables

_Exact OSQuery process, execution, handle, and runtime-artifact reference tables._

**Summary:** This page preserves the exact OSQuery source markdown for the tables in this shard. Use it as the governed exact-name reference for table and field lookup.

---

### bpf_process_events

**Platforms:** Linux

**Table Type:** EVENTED TABLE

Track time/action process executions.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| tid | BIGINT | Thread ID |
| pid | BIGINT | Process ID |
| parent | BIGINT | Parent process ID |
| uid | BIGINT | User ID |
| gid | BIGINT | Group ID |
| cid | INTEGER | Cgroup ID |
| exit_code | TEXT | Exit code of the system call |
| probe_error | INTEGER | Set to 1 if one or more buffers could not be captured |
| syscall | TEXT | System call name |
| path | TEXT | Binary path |
| cwd | TEXT | Current working directory |
| cmdline | TEXT | Command line arguments |
| duration | INTEGER | How much time was spent inside the syscall (nsecs) |
| json_cmdline | TEXT | Command line arguments, in JSON format |
| ntime | TEXT | The nsecs uptime timestamp as obtained from BPF |
| time | BIGINT | Time of execution in UNIX time |
| eid | INTEGER | Event ID |

### bpf_socket_events

**Platforms:** Linux

**Table Type:** EVENTED TABLE

Track network socket opens and closes.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| tid | BIGINT | Thread ID |
| pid | BIGINT | Process ID |
| parent | BIGINT | Parent process ID |
| uid | BIGINT | User ID |
| gid | BIGINT | Group ID |
| cid | INTEGER | Cgroup ID |
| exit_code | TEXT | Exit code of the system call |
| probe_error | INTEGER | Set to 1 if one or more buffers could not be captured |
| syscall | TEXT | System call name |
| path | TEXT | Path of executed file |
| fd | TEXT | The file description for the process socket |
| family | INTEGER | The Internet protocol family ID |
| type | INTEGER | The socket type |
| protocol | INTEGER | The network protocol ID |
| local_address | TEXT | Local address associated with socket |
| remote_address | TEXT | Remote address associated with socket |
| local_port | INTEGER | Local network protocol port number |
| remote_port | INTEGER | Remote network protocol port number |
| duration | INTEGER | How much time was spent inside the syscall (nsecs) |
| ntime | TEXT | The nsecs uptime timestamp as obtained from BPF |
| time | BIGINT | Time of execution in UNIX time |
| eid | INTEGER | Event ID |

### carves

**Platforms:** MacOS Linux Windows

List the set of completed and in-progress carves. If carve=1 then the query is treated as a new carve request.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| time | BIGINT | Time at which the carve was kicked off |
| sha256 | TEXT | A SHA256 sum of the carved archive |
| size | BIGINT | Size in bytes of the carved archive |
| path | TEXT | The path of the requested carve |
| status | TEXT | Status of the carve, can be STARTING, PENDING, SUCCESS, or FAILED |
| carve_guid | TEXT | Identifying value of the carve session |
| request_id | TEXT | Identifying value of the carve request (e.g., scheduled query name, distributed request, etc) |
| carve | INTEGER | Set this value to '1' to start a file carve |

### es_process_events

**Platforms:** MacOS

**Table Type:** EVENTED TABLE

Process execution events from EndpointSecurity.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| version | INTEGER | Version of EndpointSecurity event |
| seq_num | BIGINT | Per event sequence number |
| global_seq_num | BIGINT | Global sequence number |
| pid | BIGINT | Process (or thread) ID |
| pidversion | BIGINT | Process ID version |
| path | TEXT | Path of executed file |
| parent | BIGINT | Parent process ID |
| original_parent | BIGINT | Original parent process ID in case of reparenting |
| session_id | BIGINT | The identifier of the session that contains the process group. |
| responsible_pid | BIGINT | The pid of the process responsible for this process. |
| responsible_pidversion | BIGINT | The pidversion of the process responsible for this process. |
| parent_pidversion | BIGINT | The pidversion of the parent process. |
| cmdline | TEXT | Command line arguments (argv) |
| cmdline_count | BIGINT | Number of command line arguments |
| env | TEXT | Environment variables delimited by spaces |
| env_count | BIGINT | Number of environment variables |
| cwd | TEXT | The process current working directory |
| uid | BIGINT | User ID of the process |
| euid | BIGINT | Effective User ID of the process |
| gid | BIGINT | Group ID of the process |
| egid | BIGINT | Effective Group ID of the process |
| username | TEXT | Username |
| signing_id | TEXT | Signature identifier of the process |
| team_id | TEXT | Team identifier of the process |
| cdhash | TEXT | Codesigning hash of the process |
| platform_binary | INTEGER | Indicates if the binary is Apple signed binary (1) or not (0) |
| exit_code | INTEGER | Exit code of a process in case of an exit event |
| child_pid | BIGINT | Process ID of a child process in case of a fork event |
| time | BIGINT | Time of execution in UNIX time |
| event_type | TEXT | Type of EndpointSecurity event |
| eid | TEXT | Event ID |
| codesigning_flags | TEXT | Codesigning flags matching one of these options, in a comma separated list: NOT_VALID, ADHOC, NOT_RUNTIME, INSTALLER. See kern/cs_blobs.h in XNU for descriptions. |

### es_process_file_events

**Platforms:** MacOS

**Table Type:** EVENTED TABLE

File integrity monitoring events from EndpointSecurity including process context.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| version | INTEGER | Version of EndpointSecurity event |
| seq_num | BIGINT | Per event sequence number |
| global_seq_num | BIGINT | Global sequence number |
| pid | BIGINT | Process (or thread) ID |
| parent | BIGINT | Parent process ID |
| path | TEXT | Path of executed file |
| filename | TEXT | The source or target filename for the event |
| dest_filename | TEXT | Destination filename for the event |
| event_type | TEXT | Type of EndpointSecurity event |
| time | BIGINT | Time of execution in UNIX time |
| eid | TEXT | Event ID |

### powershell_events

**Platforms:** Windows

**Table Type:** EVENTED TABLE

Powershell script blocks reconstructed to their full script content, this table requires script block logging to be enabled.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| time | BIGINT | Timestamp the event was received by the osquery event publisher |
| datetime | TEXT | System time at which the Powershell script event occurred |
| script_block_id | TEXT | The unique GUID of the powershell script to which this block belongs |
| script_block_count | INTEGER | The total number of script blocks for this script |
| script_text | TEXT | The text content of the Powershell script |
| script_name | TEXT | The name of the Powershell script |
| script_path | TEXT | The path for the Powershell script |
| cosine_similarity | DOUBLE | How similar the Powershell script is to a provided 'normal' character frequency |

### prefetch

**Platforms:** Windows

Prefetch files show metadata related to file execution.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| path | TEXT | Prefetch file path. |
| filename | TEXT | Executable filename. |
| hash | TEXT | Prefetch CRC hash. |
| last_run_time | INTEGER | Most recent time application was run. |
| other_run_times | TEXT | Other execution times in prefetch file. |
| run_count | INTEGER | Number of times the application has been run. |
| size | INTEGER | Application file size. |
| volume_serial | TEXT | Volume serial number. |
| volume_creation | TEXT | Volume creation time. |
| accessed_files_count | INTEGER | Number of files accessed. |
| accessed_directories_count | INTEGER | Number of directories accessed. |
| accessed_files | TEXT | Files accessed by application within ten seconds of launch. |
| accessed_directories | TEXT | Directories accessed by application within ten seconds of launch. |

### process_envs

**Platforms:** MacOS Linux

A key/value table of environment variables for each process.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| pid | INTEGER | Process (or thread) ID |
| key | TEXT | Environment variable name |
| value | TEXT | Environment variable value |

### process_etw_events

**Platforms:** Windows

**Table Type:** EVENTED TABLE

Windows process execution events.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| type | TEXT | Event Type (ProcessStart, ProcessStop) |
| pid | BIGINT | Process ID |
| ppid | BIGINT | Parent Process ID |
| session_id | INTEGER | Session ID |
| flags | INTEGER | Process Flags |
| exit_code | INTEGER | Exit Code - Present only on ProcessStop events |
| path | TEXT | Path of executed binary |
| cmdline | TEXT | Command Line |
| username | TEXT | User rights - primary token username |
| token_elevation_type | TEXT | Primary token elevation type - Present only on ProcessStart events |
| token_elevation_status | INTEGER | Primary token elevation status - Present only on ProcessStart events |
| mandatory_label | TEXT | Primary token mandatory label sid - Present only on ProcessStart events |
| datetime | TEXT | Event timestamp in DATETIME format |
| time_windows | BIGINT | Event timestamp in Windows format |
| time | BIGINT | Event timestamp in Unix format |
| eid | INTEGER | Event ID |
| header_pid | BIGINT | Process ID of the process reporting the event |
| process_sequence_number | BIGINT | Process Sequence Number - Present only on ProcessStart events |
| parent_process_sequence_number | BIGINT | Parent Process Sequence Number - Present only on ProcessStart events |

### process_events

**Platforms:** MacOS Linux

**Table Type:** EVENTED TABLE

Track time/action process executions.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| pid | BIGINT | Process (or thread) ID |
| path | TEXT | Path of executed file |
| mode | TEXT | File mode permissions |
| cmdline | TEXT | Command line arguments (argv) |
| cmdline_size | BIGINT | Actual size (bytes) of command line arguments |
| env | TEXT | Environment variables delimited by spaces |
| env_count | BIGINT | Number of environment variables |
| env_size | BIGINT | Actual size (bytes) of environment list |
| cwd | TEXT | The process current working directory |
| auid | BIGINT | Audit User ID at process start |
| uid | BIGINT | User ID at process start |
| euid | BIGINT | Effective user ID at process start |
| gid | BIGINT | Group ID at process start |
| egid | BIGINT | Effective group ID at process start |
| owner_uid | BIGINT | File owner user ID |
| owner_gid | BIGINT | File owner group ID |
| atime | BIGINT | File last access in UNIX time |
| mtime | BIGINT | File modification in UNIX time |
| ctime | BIGINT | File last metadata change in UNIX time |
| btime | BIGINT | File creation in UNIX time |
| overflows | TEXT | List of structures that overflowed |
| parent | BIGINT | Process parent's PID, or -1 if cannot be determined. |
| time | BIGINT | Time of execution in UNIX time |
| uptime | BIGINT | Time of execution in system uptime |
| eid | TEXT | Event ID |
| status | BIGINT | OpenBSM Attribute: Status of the process |
| fsuid | BIGINT | Filesystem user ID at process start |
| suid | BIGINT | Saved user ID at process start |
| fsgid | BIGINT | Filesystem group ID at process start |
| sgid | BIGINT | Saved group ID at process start |
| syscall | TEXT | Syscall name: fork, vfork, clone, execve, execveat |

### process_file_events

**Platforms:** Linux

**Table Type:** EVENTED TABLE

A File Integrity Monitor implementation using the audit service.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| operation | TEXT | Operation type |
| pid | BIGINT | Process ID |
| ppid | BIGINT | Parent process ID |
| time | BIGINT | Time of execution in UNIX time |
| executable | TEXT | The executable path |
| partial | TEXT | True if this is a partial event (i.e.: this process existed before we started osquery) |
| cwd | TEXT | The current working directory of the process |
| path | TEXT | The path associated with the event |
| dest_path | TEXT | The canonical path associated with the event |
| uid | TEXT | The uid of the process performing the action |
| gid | TEXT | The gid of the process performing the action |
| auid | TEXT | Audit user ID of the process using the file |
| euid | TEXT | Effective user ID of the process using the file |
| egid | TEXT | Effective group ID of the process using the file |
| fsuid | TEXT | Filesystem user ID of the process using the file |
| fsgid | TEXT | Filesystem group ID of the process using the file |
| suid | TEXT | Saved user ID of the process using the file |
| sgid | TEXT | Saved group ID of the process using the file |
| uptime | BIGINT | Time of execution in system uptime |
| eid | TEXT | Event ID |

### process_memory_map

**Platforms:** MacOS Linux Windows

Process memory mapped files and pseudo device/regions.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| pid | INTEGER | Process (or thread) ID |
| start | TEXT | Virtual start address (hex) |
| end | TEXT | Virtual end address (hex) |
| permissions | TEXT | r=read, w=write, x=execute, p=private (cow) |
| offset | BIGINT | Offset into mapped path |
| device | TEXT | MA:MI Major/minor device ID |
| inode | INTEGER | Mapped path inode, 0 means uninitialized (BSS) |
| path | TEXT | Path to mapped file or mapped type |
| pseudo | INTEGER | 1 If path is a pseudo path, else 0 |

### process_namespaces

**Platforms:** Linux

Linux namespaces for processes running on the host system.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| pid | INTEGER | Process (or thread) ID |
| cgroup_namespace | TEXT | cgroup namespace inode |
| ipc_namespace | TEXT | ipc namespace inode |
| mnt_namespace | TEXT | mnt namespace inode |
| net_namespace | TEXT | net namespace inode |
| pid_namespace | TEXT | pid namespace inode |
| user_namespace | TEXT | user namespace inode |
| uts_namespace | TEXT | uts namespace inode |

### process_open_files

**Platforms:** MacOS Linux

File descriptors for each process.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| pid | BIGINT | Process (or thread) ID |
| fd | BIGINT | Process-specific file descriptor number |
| path | TEXT | Filesystem path of descriptor |

### process_open_handles

**Platforms:** Windows

**Status:** New

Enumerate open handles for a specified process. Defaults to the osquery process if no pid constraint is provided.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| pid | BIGINT | The process identifier that owns the handle. Required in WHERE clause |
| value | BIGINT | The handle value |
| type | TEXT | The type of object referenced by the handle. |
| access | TEXT | The access permissions of the object referenced by the handle. |
| name | TEXT | The value of the object referenced by the handle. |
| attributes | TEXT | Object handle attributes. |
| count | BIGINT | Handle Count. |
| raw_pointer_count | BIGINT | Raw Pointer/Reference Count. Meaning varies, consult Windows docs. |
| error_stage | TEXT | Error Stage. |
| error_code | BIGINT | Error Code. |

### process_open_pipes

**Platforms:** Linux

Pipes and partner processes for each process.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| pid | BIGINT | Process ID |
| fd | BIGINT | File descriptor |
| mode | TEXT | Pipe open mode (r/w) |
| inode | BIGINT | Pipe inode number |
| type | TEXT | Pipe Type: named vs unnamed/anonymous |
| partner_pid | BIGINT | Process ID of partner process sharing a particular pipe |
| partner_fd | BIGINT | File descriptor of shared pipe at partner's end |
| partner_mode | TEXT | Mode of shared pipe at partner's end |

### process_open_sockets

**Platforms:** MacOS Linux Windows

Processes which have open network sockets on the system.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| pid | INTEGER | Process (or thread) ID |
| fd | BIGINT | Socket file descriptor number |
| socket | BIGINT | Socket handle or inode number |
| family | INTEGER | Network protocol (IPv4, IPv6) |
| protocol | INTEGER | Transport protocol (TCP/UDP) |
| local_address | TEXT | Socket local address |
| remote_address | TEXT | Socket remote address |
| local_port | INTEGER | Socket local port |
| remote_port | INTEGER | Socket remote port |
| path | TEXT | For UNIX sockets (family=AF_UNIX), the domain path |
| state | TEXT | TCP socket state |
| net_namespace | TEXT | The inode number of the network namespace |

### processes

**Platforms:** MacOS Linux Windows

All running processes on the host system.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| pid | BIGINT | Process (or thread) ID |
| name | TEXT | The process path or shorthand argv[0] |
| path | TEXT | Path to executed binary |
| cmdline | TEXT | Complete argv |
| state | TEXT | Process state |
| cwd | TEXT | Process current working directory |
| root | TEXT | Process virtual root directory |
| uid | BIGINT | Unsigned user ID |
| gid | BIGINT | Unsigned group ID |
| euid | BIGINT | Unsigned effective user ID |
| egid | BIGINT | Unsigned effective group ID |
| suid | BIGINT | Unsigned saved user ID |
| sgid | BIGINT | Unsigned saved group ID |
| on_disk | INTEGER | The process path exists yes=1, no=0, unknown=-1 |
| wired_size | BIGINT | Bytes of unpageable memory used by process |
| resident_size | BIGINT | Bytes of private memory used by process |
| total_size | BIGINT | Total virtual memory size (Linux, Windows) or 'footprint' (macOS) |
| user_time | BIGINT | CPU time in milliseconds spent in user space |
| system_time | BIGINT | CPU time in milliseconds spent in kernel space |
| disk_bytes_read | BIGINT | Bytes read from disk |
| disk_bytes_written | BIGINT | Bytes written to disk |
| start_time | BIGINT | Process start time in seconds since Epoch, in case of error -1 |
| parent | BIGINT | Process parent's PID |
| pgroup | BIGINT | Process group |
| threads | INTEGER | Number of threads used by process |
| nice | INTEGER | Process nice level (-20 to 20, default 0) |
| elevated_token | INTEGER | Process uses elevated token yes=1, no=0 |
| secure_process | INTEGER | Process is secure (IUM) yes=1, no=0 |
| protection_type | TEXT | The protection type of the process |
| virtual_process | INTEGER | Process is virtual (e.g. System, Registry, vmmem) yes=1, no=0 |
| elapsed_time | BIGINT | Elapsed time in seconds this process has been running. |
| handle_count | BIGINT | Total number of handles that the process has open. This number is the sum of the handles currently opened by each thread in the process. |
| percent_processor_time | BIGINT | Returns elapsed time that all of the threads of this process used the processor to execute instructions in 100 nanoseconds ticks. |
| upid | BIGINT | A 64bit pid that is never reused. Returns -1 if we couldn't gather them from the system. |
| uppid | BIGINT | The 64bit parent pid that is never reused. Returns -1 if we couldn't gather them from the system. |
| cpu_type | INTEGER | Indicates the specific processor designed for installation. |
| cpu_subtype | INTEGER | Indicates the specific processor on which an entry may be used. |
| translated | INTEGER | Indicates whether the process is running under the Rosetta Translation Environment, yes=1, no=0, error=-1. |
| cgroup_path | TEXT | The full hierarchical path of the process's control group |

### user_events

**Platforms:** MacOS Linux

**Table Type:** EVENTED TABLE

Track user events from the audit framework.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| uid | BIGINT | User ID |
| auid | BIGINT | Audit User ID |
| pid | BIGINT | Process (or thread) ID |
| message | TEXT | Message from the event |
| type | INTEGER | The file description for the process socket |
| path | TEXT | Supplied path from event |
| address | TEXT | The Internet protocol address or family ID |
| terminal | TEXT | The network protocol ID |
| time | BIGINT | Time of execution in UNIX time |
| uptime | BIGINT | Time of execution in system uptime |
| eid | TEXT | Event ID |

### user_interaction_events

**Platforms:** MacOS

**Table Type:** EVENTED TABLE

Track user interaction events from macOS' event tapping framework.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| time | BIGINT | Time |

### winbaseobj

**Platforms:** Windows

Lists named Windows objects in the default object directories, across all terminal services sessions. Example Windows object types include Mutexes, Events, Jobs and Semaphors.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| session_id | INTEGER | Terminal Services Session Id |
| object_name | TEXT | Object Name |
| object_type | TEXT | Object Type |

<!-- DCOIR_SOURCE_END {"id":"knowledge.reference.osquery_process","sha256":"3a13d1baff6b899a6de385f67e7f54c1efc92b60c13bb2186e5429046c138a01"} -->

<!-- DCOIR_SOURCE_BEGIN {"bytes":8360,"git_blob_sha":"3d8bdba87f602e4feb7c59d5e24a691086fc2a1e","id":"knowledge.reference.osquery_index","path":"knowledge/Knowledge - Reference - OSQuery Reference Index.md","sha256":"d1c533a623a55c094dc8fcb36287b44c7d53c6243dcfe2fee17b1b6510798399"} -->
# Knowledge - Reference - OSQuery Reference Index

_Governed routing index for the sharded OSQuery schema reference set_

**Summary:** Use this page to decide which OSQuery reference shard to consult first. The detailed shard pages preserve the exact table, field, type, and description content from the approved OSQuery source markdown.

---

## Core rules

- Return raw SQL only when planning `osquery` queries.
- Do not wrap OSQuery queries in CLI syntax.
- Do not invent table names or field names.
- Use the shard pages as the governed exact-name reference when current evidence does not already provide the correct table or field.

---

## Where to start

| Investigative need | Start with | Typical examples |
| --- | --- | --- |
| Current process state, process lineage, handles, PowerShell, execution artifacts | `Knowledge - Reference - OSQuery Process and Execution Tables` | `processes`, `process_open_sockets`, `powershell_events` |
| Files, hashes, filesystem locations, mounts, partitions, file-linked events | `Knowledge - Reference - OSQuery File and Filesystem Tables` | `file`, `hash`, `mounts`, `process_file_events` |
| Ports, DNS, interfaces, routes, sockets, connectivity, Wi-Fi | `Knowledge - Reference - OSQuery Network and Connection Tables` | `listening_ports`, `dns_cache`, `interface_details` |
| Users, logons, SSH keys, auth policy, groups, and account context | `Knowledge - Reference - OSQuery User, Auth, and Account Tables` | `users`, `logged_in_users`, `user_ssh_keys` |
| Persistence, startup, services, scheduled tasks, WMI consumers, and shims | `Knowledge - Reference - OSQuery Persistence and Startup Tables` | `scheduled_tasks`, `services`, `wmi_event_filters` |
| System, OS, hardware, memory, uptime, USB, and platform details | `Knowledge - Reference - OSQuery System, Hardware, and Platform Tables` | `system_info`, `os_version`, `usb_devices` |
| Security telemetry, event tables, firewall, YARA, Gatekeeper, and AppArmor | `Knowledge - Reference - OSQuery Security, Detection, and Event Tables` | `windows_eventlog`, `yara_process`, `apparmor_events` |
| Installed apps, packages, browser extensions, and program inventory | `Knowledge - Reference - OSQuery Application, Package, and Extension Tables` | `programs`, `deb_packages`, `chrome_extensions` |
| Containers, LXD, Docker, cloud metadata, and OSQuery self-state | `Knowledge - Reference - OSQuery Virtualization, Cloud, and Container Tables` | `docker_containers`, `ec2_instance_metadata`, `osquery_info` |

---

## Shard inventory
- `Knowledge - Reference - OSQuery Process and Execution Tables`: `bpf_process_events`, `bpf_socket_events`, `carves`, `es_process_events`, `es_process_file_events`, `powershell_events`, `prefetch`, `process_envs`, `process_etw_events`, `process_events`, `process_file_events`, `process_memory_map`, `process_namespaces`, `process_open_files`, `process_open_handles`, `process_open_pipes`, `process_open_sockets`, `processes`, `user_events`, `user_interaction_events`, `winbaseobj`
- `Knowledge - Reference - OSQuery File and Filesystem Tables`: `block_devices`, `deb_package_files`, `device_file`, `device_hash`, `device_partitions`, `deviceguard_status`, `disk_events`, `disk_info`, `extended_attributes`, `file`, `hash`, `magic`, `md_devices`, `md_drives`, `md_personalities`, `mdfind`, `mdls`, `mounts`, `nfs_shares`, `ntfs_acl_permissions`, `ntfs_journal_events`, `package_bom`, `package_install_history`, `plist`, `quicklook_cache`, `recent_files`, `rpm_package_files`, `shared_memory`, `shared_resources`, `smbios_tables`, `yara_file`
- `Knowledge - Reference - OSQuery Network and Connection Tables`: `arp_cache`, `connectivity`, `curl`, `curl_certificate`, `dns_cache`, `dns_lookup_events`, `dns_resolvers`, `etc_hosts`, `etc_protocols`, `etc_services`, `interface_addresses`, `interface_details`, `interface_ipv6`, `iptables`, `listening_ports`, `pipes`, `routes`, `socket_events`, `wifi_networks`, `wifi_status`, `wifi_survey`
- `Knowledge - Reference - OSQuery User, Auth, and Account Tables`: `account_policy_data`, `ad_config`, `authorization_mechanisms`, `authorizations`, `authorized_keys`, `default_environment`, `groups`, `known_hosts`, `last`, `location_services`, `logged_in_users`, `logon_sessions`, `managed_policies`, `ntdomains`, `office_mru`, `password_policy`, `preferences`, `screenlock`, `shadow`, `shared_folders`, `sharing_preferences`, `shell_history`, `shellbags`, `ssh_configs`, `sudoers`, `user_groups`, `user_ssh_keys`, `userassist`, `users`
- `Knowledge - Reference - OSQuery Persistence and Startup Tables`: `appcompat_shims`, `autoexec`, `background_activities_moderator`, `browser_plugins`, `chrome_extension_content_scripts`, `drivers`, `event_taps`, `kernel_extensions`, `kernel_modules`, `launchd`, `launchd_overrides`, `scheduled_tasks`, `services`, `shimcache`, `startup_items`, `system_extensions`, `systemd_units`, `wmi_cli_event_consumers`, `wmi_event_filters`, `wmi_filter_consumer_binding`, `wmi_script_event_consumers`
- `Knowledge - Reference - OSQuery System, Hardware, and Platform Tables`: `acpi_tables`, `augeas`, `battery`, `carbon_black_info`, `chassis_info`, `connected_displays`, `cpu_info`, `cpu_time`, `cpuid`, `crashes`, `crontab`, `device_firmware`, `fan_speed_sensors`, `hardware_events`, `ibridge_info`, `intel_me_info`, `iokit_devicetree`, `iokit_registry`, `kernel_info`, `kernel_panics`, `kva_speculative_info`, `load_average`, `logical_drives`, `memory_array_mapped_addresses`, `memory_arrays`, `memory_device_mapped_addresses`, `memory_devices`, `memory_error_info`, `memory_info`, `memory_map`, `msr`, `nvram`, `oem_strings`, `os_version`, `pci_devices`, `physical_disk_performance`, `platform_info`, `power_sensors`, `registry`, `secureboot`, `secureboot_certificates`, `smc_keys`, `suid_bin`, `system_controls`, `system_info`, `system_profiler`, `temperature_sensors`, `time`, `time_machine_backups`, `time_machine_destinations`, `tpm_info`, `ulimit_info`, `uptime`, `usb_devices`, `video_info`, `virtual_memory_info`, `windows_crashes`, `wmi_bios_info`
- `Knowledge - Reference - OSQuery Security, Detection, and Event Tables`: `alf`, `alf_exceptions`, `alf_explicit_auths`, `apparmor_events`, `apparmor_profiles`, `asl`, `authenticode`, `bitlocker_info`, `certificate_trust_settings`, `certificates`, `disk_encryption`, `file_events`, `gatekeeper`, `gatekeeper_approved_apps`, `kernel_keys`, `keychain_acls`, `keychain_items`, `sandboxes`, `seccomp_events`, `security_profile_info`, `selinux_events`, `selinux_settings`, `signature`, `sip_config`, `syslog_events`, `unified_log`, `windows_eventlog`, `windows_events`, `windows_firewall_rules`, `windows_security_center`, `windows_security_products`, `xprotect_entries`, `xprotect_meta`, `xprotect_reports`, `yara_events`, `yara_process`
- `Knowledge - Reference - OSQuery Application, Package, and Extension Tables`: `app_schemes`, `apps`, `apt_sources`, `chocolatey_packages`, `chrome_extensions`, `cups_destinations`, `cups_jobs`, `deb_packages`, `firefox_addons`, `homebrew_packages`, `ie_extensions`, `jetbrains_plugins`, `npm_packages`, `package_receipts`, `patches`, `portage_keywords`, `portage_packages`, `portage_use`, `programs`, `python_packages`, `rpm_packages`, `running_apps`, `safari_extensions`, `vscode_extensions`, `windows_optional_features`, `windows_search`, `windows_update_history`, `yum_sources`
- `Knowledge - Reference - OSQuery Virtualization, Cloud, and Container Tables`: `azure_instance_metadata`, `azure_instance_tags`, `docker_container_envs`, `docker_container_fs_changes`, `docker_container_labels`, `docker_container_mounts`, `docker_container_networks`, `docker_container_ports`, `docker_container_processes`, `docker_container_stats`, `docker_containers`, `docker_image_history`, `docker_image_labels`, `docker_image_layers`, `docker_images`, `docker_info`, `docker_network_labels`, `docker_networks`, `docker_version`, `docker_volume_labels`, `docker_volumes`, `ec2_instance_metadata`, `ec2_instance_tags`, `lxd_certificates`, `lxd_cluster`, `lxd_cluster_members`, `lxd_images`, `lxd_instance_config`, `lxd_instance_devices`, `lxd_instances`, `lxd_networks`, `lxd_storage_pools`, `osquery_events`, `osquery_extensions`, `osquery_flags`, `osquery_info`, `osquery_packs`, `osquery_registry`, `osquery_schedule`, `prometheus_metrics`, `ycloud_instance_metadata`

<!-- DCOIR_SOURCE_END {"id":"knowledge.reference.osquery_index","sha256":"d1c533a623a55c094dc8fcb36287b44c7d53c6243dcfe2fee17b1b6510798399"} -->

<!-- DCOIR_SOURCE_BEGIN {"bytes":30325,"git_blob_sha":"ff35f8dffc93481c6ea34422f4630afb3b0d0cab","id":"knowledge.reference.osquery_security","path":"knowledge/Knowledge - Reference - OSQuery Security, Detection, and Event Tables.md","sha256":"8ce268e94e37b90ad64b099504caf17d15ca3a6ac416d28b16d8c48c9a0754e5"} -->
# Knowledge - Reference - OSQuery Security, Detection, and Event Tables

_Exact OSQuery security, detection, audit, firewall, and event reference tables._

**Summary:** This page preserves the exact OSQuery source markdown for the tables in this shard. Use it as the governed exact-name reference for table and field lookup.

---

### alf

**Platforms:** MacOS

macOS application layer firewall (ALF) service details.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| allow_signed_enabled | INTEGER | 1 If allow signed mode is enabled else 0 (not supported on macOS 15+) |
| firewall_unload | INTEGER | 1 If firewall unloading enabled else 0 (not supported on macOS 15+) |
| global_state | INTEGER | 1 If the firewall is enabled with exceptions, 2 if the firewall is configured to block all incoming connections, else 0 |
| logging_enabled | INTEGER | 1 If logging mode is enabled else 0 |
| logging_option | INTEGER | Firewall logging option (not supported on macOS 15+) |
| stealth_enabled | INTEGER | 1 If stealth mode is enabled else 0 |
| version | TEXT | Application Layer Firewall version |

### alf_exceptions

**Platforms:** MacOS

macOS application layer firewall (ALF) service exceptions.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| path | TEXT | Path to the executable that is excepted. On macOS 15+ this can also be a bundle identifier |
| state | INTEGER | Firewall exception state. 0 if the application is configured to allow incoming connections, 2 if the application is configured to block incoming connections and 3 if the application is configuted to allow incoming connections but with additional restrictions. |

### alf_explicit_auths

**Platforms:** MacOS

ALF services explicitly allowed to perform networking. Not supported on macOS 15+ (returns no results).

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| process | TEXT | Process name that is explicitly allowed |

### apparmor_events

**Platforms:** Linux

**Table Type:** EVENTED TABLE

Track AppArmor events.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| type | TEXT | Event type |
| message | TEXT | Raw audit message |
| time | BIGINT | Time of execution in UNIX time |
| uptime | BIGINT | Time of execution in system uptime |
| eid | TEXT | Event ID |
| apparmor | TEXT | Apparmor Status like ALLOWED, DENIED etc. |
| operation | TEXT | Permission requested by the process |
| parent | UNSIGNED_BIGINT | Parent process PID |
| profile | TEXT | Apparmor profile name |
| name | TEXT | Process name |
| pid | UNSIGNED_BIGINT | Process ID |
| comm | TEXT | Command-line name of the command that was used to invoke the analyzed process |
| denied_mask | TEXT | Denied permissions for the process |
| capname | TEXT | Capability requested by the process |
| fsuid | UNSIGNED_BIGINT | Filesystem user ID |
| ouid | UNSIGNED_BIGINT | Object owner's user ID |
| capability | BIGINT | Capability number |
| requested_mask | TEXT | Requested access mask |
| info | TEXT | Additional information |
| error | TEXT | Error information |
| namespace | TEXT | AppArmor namespace |
| label | TEXT | AppArmor label |

### apparmor_profiles

**Platforms:** Linux

Track active AppArmor profiles.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| path | TEXT | Unique, aa-status compatible, policy identifier. |
| name | TEXT | Policy name. |
| attach | TEXT | Which executable(s) a profile will attach to. |
| mode | TEXT | How the policy is applied. |
| sha1 | TEXT | A unique hash that identifies this policy. |
| sha256 | TEXT | A unique hash that identifies this policy. |

### asl

**Platforms:** MacOS

Queries the Apple System Log data structure for system events.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| time | INTEGER | Unix timestamp. Set automatically |
| time_nano_sec | INTEGER | Nanosecond time. |
| host | TEXT | Sender's address (set by the server). |
| sender | TEXT | Sender's identification string. Default is process name. |
| facility | TEXT | Sender's facility. Default is 'user'. |
| pid | INTEGER | Sending process ID encoded as a string. Set automatically. |
| gid | BIGINT | GID that sent the log message (set by the server). |
| uid | BIGINT | UID that sent the log message (set by the server). |
| level | INTEGER | Log level number. See levels in asl.h. |
| message | TEXT | Message text. |
| ref_pid | INTEGER | Reference PID for messages proxied by launchd |
| ref_proc | TEXT | Reference process for messages proxied by launchd |
| extra | TEXT | Extra columns, in JSON format. Queries against this column are performed entirely in SQLite, so do not benefit from efficient querying via asl.h. |

### authenticode

**Platforms:** Windows

File (executable, bundle, installer, disk) code signing status.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| path | TEXT | Must provide a path or directory Required in WHERE clause |
| original_program_name | TEXT | The original program name that the publisher has signed |
| serial_number | TEXT | The certificate serial number |
| issuer_name | TEXT | The certificate issuer name |
| subject_name | TEXT | The certificate subject name |
| result | TEXT | The signature check result |

### bitlocker_info

**Platforms:** Windows

Retrieve bitlocker status of the machine.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| device_id | TEXT | ID of the encrypted drive. |
| drive_letter | TEXT | Drive letter of the encrypted drive. |
| persistent_volume_id | TEXT | Persistent ID of the drive. |
| conversion_status | INTEGER | The bitlocker conversion status of the drive. |
| protection_status | INTEGER | The bitlocker protection status of the drive. |
| encryption_method | TEXT | The encryption type of the device. |
| version | INTEGER | The FVE metadata version of the drive. |
| percentage_encrypted | INTEGER | The percentage of the drive that is encrypted. |
| lock_status | INTEGER | The accessibility status of the drive from Windows. |

### certificate_trust_settings

**Platforms:** MacOS

Certificate Authorities trust settings installed in Keychains/ca-bundles.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| common_name | TEXT | Certificate common name |
| serial | TEXT | Certificate serial number |
| trust_domain | TEXT | Certificate trust settings domain |
| trust_policy_name | TEXT | Certificate trust policy name |
| trust_policy_data | TEXT | Certificate trust policy data |
| trust_allowed_error | TEXT | Certificate trust allowed error |
| trust_key_usage | TEXT | Certificate trust key usage |
| trust_result | TEXT | Certificate trust result |

### certificates

**Platforms:** MacOS Linux Windows

Certificate Authorities installed in Keychains/ca-bundles. NOTE: osquery limits frequent access to keychain files on macOS. This limit is controlled by keychain_access_interval flag. On macOS, 'path' may point to either a keychain file or a DER/PEM-encoded certificate file; non-keychain files are parsed as DER/PEM.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| common_name | TEXT | Certificate CommonName |
| subject | TEXT | Certificate distinguished name (deprecated, use subject2) |
| issuer | TEXT | Certificate issuer distinguished name (deprecated, use issuer2) |
| ca | INTEGER | 1 if CA: true (certificate is an authority) else 0 |
| self_signed | INTEGER | 1 if self-signed, else 0 |
| not_valid_before | TEXT | Lower bound of valid date |
| not_valid_after | TEXT | Certificate expiration data |
| signing_algorithm | TEXT | Signing algorithm used |
| key_algorithm | TEXT | Key algorithm used |
| key_strength | TEXT | Key size used for RSA/DSA, or curve name |
| key_usage | TEXT | Certificate key usage and extended key usage |
| subject_key_id | TEXT | SKID an optionally included SHA1 |
| authority_key_id | TEXT | AKID an optionally included SHA1 |
| sha1 | TEXT | SHA1 hash of the raw certificate contents |
| path | TEXT | Path to Keychain or PEM bundle |
| serial | TEXT | Certificate serial number |
| sid | TEXT | SID |
| store_location | TEXT | Certificate system store location |
| store | TEXT | Certificate system store |
| username | TEXT | Username |
| store_id | TEXT | Exists for service/user stores. Contains raw store id provided by WinAPI. |
| issuer2 | TEXT | Certificate issuer distinguished name |
| subject2 | TEXT | Certificate distinguished name |

### disk_encryption

**Platforms:** MacOS Linux

Disk encryption status and information.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Disk name |
| uuid | TEXT | Disk Universally Unique Identifier |
| encrypted | INTEGER | 1 If encrypted: true (disk is encrypted), else 0 |
| type | TEXT | Description of cipher type and mode if available |
| encryption_status | TEXT | Disk encryption status with one of following values: encrypted \| not encrypted \| undefined |
| uid | TEXT | Currently authenticated user if available |
| user_uuid | TEXT | UUID of authenticated user if available |
| filevault_status | TEXT | FileVault status with one of following values: on \| off \| unknown |

### file_events

**Platforms:** MacOS Linux

**Table Type:** EVENTED TABLE

Track time/action changes to files specified in configuration data.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| target_path | TEXT | The path associated with the event |
| category | TEXT | The category of the file defined in the config |
| action | TEXT | Change action (UPDATE, REMOVE, etc) |
| transaction_id | BIGINT | ID used during bulk update |
| inode | BIGINT | Filesystem inode number |
| uid | BIGINT | Owning user ID |
| gid | BIGINT | Owning group ID |
| mode | TEXT | Permission bits |
| size | BIGINT | Size of file in bytes |
| atime | BIGINT | Last access time |
| mtime | BIGINT | Last modification time |
| ctime | BIGINT | Last status change time |
| md5 | TEXT | The MD5 of the file after change |
| sha1 | TEXT | The SHA1 of the file after change |
| sha256 | TEXT | The SHA256 of the file after change |
| hashed | INTEGER | 1 if the file was hashed, 0 if not, -1 if hashing failed |
| time | BIGINT | Time of file event |
| eid | TEXT | Event ID |

### gatekeeper

**Platforms:** MacOS

macOS Gatekeeper Details.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| assessments_enabled | INTEGER | 1 If a Gatekeeper is enabled else 0 |
| dev_id_enabled | INTEGER | 1 If a Gatekeeper allows execution from identified developers else 0 |
| version | TEXT | Version of Gatekeeper's gke.bundle |
| opaque_version | TEXT | Version of Gatekeeper's gkopaque.bundle |

### gatekeeper_approved_apps

**Platforms:** MacOS

Gatekeeper apps a user has allowed to run.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| path | TEXT | Path of executable allowed to run |
| requirement | TEXT | Code signing requirement language |
| ctime | DOUBLE | Last change time |
| mtime | DOUBLE | Last modification time |

### kernel_keys

**Platforms:** Linux

List of security data, authentication keys and encryption keys.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| serial_number | TEXT | The serial key of the key. |
| flags | TEXT | A set of flags describing the state of the key. |
| usage | BIGINT | the number of threads and open file references that refer to this key. |
| timeout | TEXT | The amount of time until the key will expire, expressed in human-readable form. The string perm here means that the key is permanent (no timeout). The string expd means that the key has already expired. |
| permissions | TEXT | The key permissions, expressed as four hexadecimal bytes containing, from left to right, the possessor, user, group, and other permissions. |
| uid | BIGINT | The user ID of the key owner. |
| gid | BIGINT | The group ID of the key. |
| type | TEXT | The key type. |
| description | TEXT | The key description. |

### keychain_acls

**Platforms:** MacOS

Applications that have ACL entries in the keychain. NOTE: osquery limits frequent access to keychain files. This limit is controlled by keychain_access_interval flag.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| keychain_path | TEXT | The path of the keychain |
| authorizations | TEXT | A space delimited set of authorization attributes |
| path | TEXT | The path of the authorized application |
| description | TEXT | The description included with the ACL entry |
| label | TEXT | An optional label tag that may be included with the keychain entry |

### keychain_items

**Platforms:** MacOS

Generic details about keychain items. NOTE: osquery limits frequent access to keychain files. This limit is controlled by keychain_access_interval flag.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| label | TEXT | Generic item name |
| description | TEXT | Optional item description |
| comment | TEXT | Optional keychain comment |
| account | TEXT | Optional item account |
| created | TEXT | Date item was created |
| modified | TEXT | Date of last modification |
| type | TEXT | Keychain item type (class) |
| pk_hash | TEXT | Hash of associated public key (SHA1 of subjectPublicKey, see RFC 8520 4.2.1.2) |
| path | TEXT | Path to keychain containing item |

### sandboxes

**Platforms:** MacOS

macOS application sandboxes container details.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| label | TEXT | UTI-format bundle or label ID |
| user | TEXT | Sandbox owner |
| enabled | INTEGER | Application sandboxings enabled on container |
| build_id | TEXT | Sandbox-specific identifier |
| bundle_path | TEXT | Application bundle used by the sandbox |
| path | TEXT | Path to sandbox container directory |

### seccomp_events

**Platforms:** Linux

**Table Type:** EVENTED TABLE

A virtual table that tracks seccomp events.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| time | BIGINT | Time of execution in UNIX time |
| uptime | BIGINT | Time of execution in system uptime |
| auid | UNSIGNED_BIGINT | Audit user ID (loginuid) of the user who started the analyzed process |
| uid | UNSIGNED_BIGINT | User ID of the user who started the analyzed process |
| gid | UNSIGNED_BIGINT | Group ID of the user who started the analyzed process |
| ses | UNSIGNED_BIGINT | Session ID of the session from which the analyzed process was invoked |
| pid | UNSIGNED_BIGINT | Process ID |
| comm | TEXT | Command-line name of the command that was used to invoke the analyzed process |
| exe | TEXT | The path to the executable that was used to invoke the analyzed process |
| sig | BIGINT | Signal value sent to process by seccomp |
| arch | TEXT | Information about the CPU architecture |
| syscall | TEXT | Type of the system call |
| compat | BIGINT | Is system call in compatibility mode |
| ip | TEXT | Instruction pointer value |
| code | TEXT | The seccomp action |

### security_profile_info

**Platforms:** Windows

Information on the security profile of a given system by listing the system Account and Audit Policies. This table mimics the exported securitypolicy output from the secedit tool.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| minimum_password_age | INTEGER | Determines the minimum number of days that a password must be used before the user can change it |
| maximum_password_age | INTEGER | Determines the maximum number of days that a password can be used before the client requires the user to change it |
| minimum_password_length | INTEGER | Determines the least number of characters that can make up a password for a user account |
| password_complexity | INTEGER | Determines whether passwords must meet a series of strong-password guidelines |
| password_history_size | INTEGER | Number of unique new passwords that must be associated with a user account before an old password can be reused |
| lockout_bad_count | INTEGER | Number of failed logon attempts after which a user account MUST be locked out |
| logon_to_change_password | INTEGER | Determines if logon session is required to change the password |
| force_logoff_when_expire | INTEGER | Determines whether SMB client sessions with the SMB server will be forcibly disconnected when the client's logon hours expire |
| new_administrator_name | TEXT | Determines the name of the Administrator account on the local computer |
| new_guest_name | TEXT | Determines the name of the Guest account on the local computer |
| clear_text_password | INTEGER | Determines whether passwords MUST be stored by using reversible encryption |
| lsa_anonymous_name_lookup | INTEGER | Determines if an anonymous user is allowed to query the local LSA policy |
| enable_admin_account | INTEGER | Determines whether the Administrator account on the local computer is enabled |
| enable_guest_account | INTEGER | Determines whether the Guest account on the local computer is enabled |
| audit_system_events | INTEGER | Determines whether the operating system MUST audit System Change, System Startup, System Shutdown, Authentication Component Load, and Loss or Excess of Security events |
| audit_logon_events | INTEGER | Determines whether the operating system MUST audit each instance of a user attempt to log on or log off this computer |
| audit_object_access | INTEGER | Determines whether the operating system MUST audit each instance of user attempts to access a non-Active Directory object that has its own SACL specified |
| audit_privilege_use | INTEGER | Determines whether the operating system MUST audit each instance of user attempts to exercise a user right |
| audit_policy_change | INTEGER | Determines whether the operating system MUST audit each instance of user attempts to change user rights assignment policy, audit policy, account policy, or trust policy |
| audit_account_manage | INTEGER | Determines whether the operating system MUST audit each event of account management on a computer |
| audit_process_tracking | INTEGER | Determines whether the operating system MUST audit process-related events |
| audit_ds_access | INTEGER | Determines whether the operating system MUST audit each instance of user attempts to access an Active Directory object that has its own system access control list (SACL) specified |
| audit_account_logon | INTEGER | Determines whether the operating system MUST audit each time this computer validates the credentials of an account |

### selinux_events

**Platforms:** Linux

**Table Type:** EVENTED TABLE

Track SELinux events.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| type | TEXT | Event type |
| message | TEXT | Message |
| time | BIGINT | Time of execution in UNIX time |
| uptime | BIGINT | Time of execution in system uptime |
| eid | TEXT | Event ID |

### selinux_settings

**Platforms:** Linux

Track active SELinux settings.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| scope | TEXT | Where the key is located inside the SELinuxFS mount point. |
| key | TEXT | Key or class name. |
| value | TEXT | Active value. |

### signature

**Platforms:** MacOS

File (executable, bundle, installer, disk) code signing status.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| path | TEXT | Must provide a path or directory Required in WHERE clause |
| hash_resources | INTEGER | Set to 1 to also hash resources, or 0 otherwise. Default is 1 |
| hash_executable | INTEGER | Set to 1 to also hash the executable, or 0 otherwise. Default is 1 |
| arch | TEXT | If applicable, the arch of the signed code |
| signed | INTEGER | 1 If the file is signed else 0 |
| identifier | TEXT | The signing identifier sealed into the signature |
| cdhash | TEXT | Hash of the application Code Directory |
| team_identifier | TEXT | The team signing identifier sealed into the signature |
| authority | TEXT | Certificate Common Name |
| entitlements | TEXT | JSON representation of the code signing entitlements |

### sip_config

**Platforms:** MacOS

Apple's System Integrity Protection (rootless) status.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| config_flag | TEXT | The System Integrity Protection config flag |
| enabled | INTEGER | 1 if this configuration is enabled, otherwise 0 |
| enabled_nvram | INTEGER | 1 if this configuration is enabled, otherwise 0 |

### syslog_events

**Platforms:** Linux

**Table Type:** EVENTED TABLE

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| time | BIGINT | Current unix epoch time |
| datetime | TEXT | Time known to syslog |
| host | TEXT | Hostname configured for syslog |
| severity | INTEGER | Syslog severity |
| facility | TEXT | Syslog facility |
| tag | TEXT | The syslog tag |
| message | TEXT | The syslog message |
| eid | TEXT | Event ID |

### unified_log

**Platforms:** MacOS

Queries the OSLog framework for entries in the system log. The maximum number of rows returned is limited for performance issues. Use timestamp > or >= constraints to optimize query performance. This table introduces a new idiom for extracting sequential data in batches using multiple queries, ordered by timestamp. To trigger it, the user should include the condition "timestamp > -1", and the table will handle pagination. Note that the saved pagination counter is incremented globally across all queries and table invocations within a query. To avoid multiple table invocations within a query, use only AND and = constraints in WHERE clause.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| timestamp | BIGINT | unix timestamp associated with the entry |
| timestamp_double | TEXT | floating point timestamp associated with the entry |
| storage | INTEGER | the storage category for the entry |
| message | TEXT | composed message |
| activity | BIGINT | the activity ID associate with the entry |
| process | TEXT | the name of the process that made the entry |
| pid | BIGINT | the pid of the process that made the entry |
| sender | TEXT | the name of the binary image that made the entry |
| tid | BIGINT | the tid of the thread that made the entry |
| category | TEXT | the category of the os_log_t used |
| subsystem | TEXT | the subsystem of the os_log_t used |
| level | TEXT | the severity level of the entry (undefined, debug, info, default, error, fault) |
| max_rows | INTEGER | the max number of rows returned (defaults to 100) |
| predicate | TEXT | predicate to search (see `log help predicates`), note that this is merged into the predicate created from the column constraints |

### windows_eventlog

**Platforms:** Windows

Table for querying all recorded Windows event logs.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| channel | TEXT | Source or channel of the event Required in WHERE clause |
| datetime | TEXT | System time at which the event occurred |
| task | INTEGER | Task value associated with the event |
| level | INTEGER | Severity level associated with the event |
| provider_name | TEXT | Provider name of the event |
| provider_guid | TEXT | Provider guid of the event |
| computer_name | TEXT | Hostname of system where event was generated |
| eventid | INTEGER | Event ID of the event |
| keywords | TEXT | A bitmask of the keywords defined in the event |
| data | TEXT | Data associated with the event |
| pid | INTEGER | Process ID which emitted the event record |
| tid | INTEGER | Thread ID which emitted the event record |
| time_range | TEXT | System time to selectively filter the events |
| timestamp | TEXT | Timestamp to selectively filter the events |
| xpath | TEXT | The custom query to filter events Required in WHERE clause |

### windows_events

**Platforms:** Windows

**Table Type:** EVENTED TABLE

Windows Event logs.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| time | BIGINT | Timestamp the event was received |
| datetime | TEXT | System time at which the event occurred |
| source | TEXT | Source or channel of the event |
| provider_name | TEXT | Provider name of the event |
| provider_guid | TEXT | Provider guid of the event |
| computer_name | TEXT | Hostname of system where event was generated |
| eventid | INTEGER | Event ID of the event |
| task | INTEGER | Task value associated with the event |
| level | INTEGER | The severity level associated with the event |
| keywords | TEXT | A bitmask of the keywords defined in the event |
| data | TEXT | Data associated with the event |
| eid | TEXT | Event ID |

### windows_firewall_rules

**Platforms:** Windows

Provides the list of Windows firewall rules.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Friendly name of the rule |
| app_name | TEXT | Friendly name of the application to which the rule applies |
| action | TEXT | Action for the rule or default setting |
| enabled | INTEGER | 1 if the rule is enabled |
| grouping | TEXT | Group to which an individual rule belongs |
| direction | TEXT | Direction of traffic for which the rule applies |
| protocol | TEXT | IP protocol of the rule |
| local_addresses | TEXT | Local addresses for the rule |
| remote_addresses | TEXT | Remote addresses for the rule |
| local_ports | TEXT | Local ports for the rule |
| remote_ports | TEXT | Remote ports for the rule |
| icmp_types_codes | TEXT | ICMP types and codes for the rule |
| profile_domain | INTEGER | 1 if the rule profile type is domain |
| profile_private | INTEGER | 1 if the rule profile type is private |
| profile_public | INTEGER | 1 if the rule profile type is public |
| service_name | TEXT | Service name property of the application |

### windows_security_center

**Platforms:** Windows

The health status of Window Security features. Health values can be "Good", "Poor". "Snoozed", "Not Monitored", and "Error".

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| firewall | TEXT | The health of the monitored Firewall (see windows_security_products) |
| autoupdate | TEXT | The health of the Windows Autoupdate feature |
| antivirus | TEXT | The health of the monitored Antivirus solution (see windows_security_products) |
| antispyware | TEXT | Deprecated (always 'Good'). |
| internet_settings | TEXT | The health of the Internet Settings |
| windows_security_center_service | TEXT | The health of the Windows Security Center Service |
| user_account_control | TEXT | The health of the User Account Control (UAC) capability in Windows |

### windows_security_products

**Platforms:** Windows

Enumeration of registered Windows security products. Note: Not compatible with Windows Server.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| type | TEXT | Type of security product |
| name | TEXT | Name of product |
| state | TEXT | State of protection |
| state_timestamp | TEXT | Timestamp for the product state |
| remediation_path | TEXT | Remediation path |
| signatures_up_to_date | INTEGER | 1 if product signatures are up to date, else 0 |

### xprotect_entries

**Platforms:** MacOS

Database of the machine's XProtect signatures.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Description of XProtected malware |
| launch_type | TEXT | Launch services content type |
| identity | TEXT | XProtect identity (SHA1) of content |
| filename | TEXT | Use this file name to match |
| filetype | TEXT | Use this file type to match |
| optional | INTEGER | Match any of the identities/patterns for this XProtect name |
| uses_pattern | INTEGER | Uses a match pattern instead of identity |

### xprotect_meta

**Platforms:** MacOS

Database of the machine's XProtect browser-related signatures.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| identifier | TEXT | Browser plugin or extension identifier |
| type | TEXT | Either plugin or extension |
| developer_id | TEXT | Developer identity (SHA1) of extension |
| min_version | TEXT | The minimum allowed plugin version. |

### xprotect_reports

**Platforms:** MacOS

Database of XProtect matches (if user generated/sent an XProtect report).

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Description of XProtected malware |
| user_action | TEXT | Action taken by user after prompted |
| time | TEXT | Quarantine alert time |

### yara_events

**Platforms:** MacOS Linux Windows

**Table Type:** EVENTED TABLE

Track YARA matches for files specified in configuration data.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| target_path | TEXT | The path scanned |
| category | TEXT | The category of the file |
| action | TEXT | Change action (UPDATE, REMOVE, etc) |
| matches | TEXT | List of YARA matches |
| count | INTEGER | Number of YARA matches |
| strings | TEXT | Matching strings |
| tags | TEXT | Matching tags |
| time | BIGINT | Time of the scan |
| eid | TEXT | Event ID |
| transaction_id | BIGINT | ID used during bulk update |

### yara_process

**Platforms:** MacOS Linux Windows

**Status:** New

Triggers one-off YARA query for process memory of the specified pid. Additionally requires one of `sig_group`, `sigfile`, or `sigrule`.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| pid | INTEGER | The pid scanned (process memory) Required in WHERE clause |
| matches | TEXT | List of YARA matches |
| count | INTEGER | Number of YARA matches |
| sig_group | TEXT | Signature group used |
| sigfile | TEXT | Signature file used |
| sigrule | TEXT | Signature strings used |
| strings | TEXT | Matching strings |
| tags | TEXT | Matching tags |
| sigurl | TEXT | Signature url |
| pid_with_namespace | INTEGER | Pids that contain a namespace |

<!-- DCOIR_SOURCE_END {"id":"knowledge.reference.osquery_security","sha256":"8ce268e94e37b90ad64b099504caf17d15ca3a6ac416d28b16d8c48c9a0754e5"} -->

<!-- DCOIR_SOURCE_BEGIN {"bytes":46782,"git_blob_sha":"8fb2e8eb598648319152037ef25b4039871a19d0","id":"knowledge.reference.osquery_system","path":"knowledge/Knowledge - Reference - OSQuery System, Hardware, and Platform Tables.md","sha256":"675e8fc0dfea1cedde605daf06537db132b12e1943f16f5e08cd36d04737670d"} -->
# Knowledge - Reference - OSQuery System, Hardware, and Platform Tables

_Exact OSQuery system, OS, hardware, memory, uptime, and platform reference tables._

**Summary:** This page preserves the exact OSQuery source markdown for the tables in this shard. Use it as the governed exact-name reference for table and field lookup.

---

### acpi_tables

**Platforms:** MacOS Linux

Firmware ACPI functional table common metadata and content.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | ACPI table name |
| size | INTEGER | Size of compiled table data |
| md5 | TEXT | MD5 hash of table content |

### augeas

**Platforms:** MacOS Linux

Configuration files parsed by augeas.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| node | TEXT | The node path of the configuration item |
| value | TEXT | The value of the configuration item |
| label | TEXT | The label of the configuration item |
| path | TEXT | The path to the configuration file |

### battery

**Platforms:** MacOS Windows

Provides information about the internal battery of a laptop. Note: On Windows, columns with Ah or mAh units assume that the battery is 12V.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| manufacturer | TEXT | The battery manufacturer's name |
| model | TEXT | The battery's model number |
| serial_number | TEXT | The battery's serial number |
| cycle_count | INTEGER | The number of charge/discharge cycles |
| state | TEXT | One of the following: "AC Power" indicates the battery is connected to an external power source, "Battery Power" indicates that the battery is drawing internal power, "Off Line" indicates the battery is off-line or no longer connected |
| charging | INTEGER | 1 if the battery is currently being charged by a power source. 0 otherwise |
| charged | INTEGER | 1 if the battery is currently completely charged. 0 otherwise |
| designed_capacity | INTEGER | The battery's designed capacity in mAh |
| max_capacity | INTEGER | The battery's actual capacity when it is fully charged in mAh |
| current_capacity | INTEGER | The battery's current capacity (level of charge) in mAh |
| percent_remaining | INTEGER | The percentage of battery remaining before it is drained |
| amperage | INTEGER | The current amperage in/out of the battery in mA (positive means charging, negative means discharging) |
| voltage | INTEGER | The battery's current voltage in mV |
| minutes_until_empty | INTEGER | The number of minutes until the battery is fully depleted. This value is -1 if this time is still being calculated |
| minutes_to_full_charge | INTEGER | The number of minutes until the battery is fully charged. This value is -1 if this time is still being calculated. On Windows this is calculated from the charge rate and capacity and may not agree with the number reported in "Power & Battery" |
| chemistry | TEXT | The battery chemistry type (eg. LiP). Some possible values are documented in https://learn.microsoft.com/en-us/windows/win32/power/battery-information-str. |
| health | TEXT | One of the following: "Good" describes a well-performing battery, "Fair" describes a functional battery with limited capacity, or "Poor" describes a battery that's not capable of providing power |
| condition | TEXT | One of the following: "Normal" indicates the condition of the battery is within normal tolerances, "Service Needed" indicates that the battery should be checked out by a licensed Mac repair service, "Permanent Failure" indicates the battery needs replacement |
| manufacture_date | INTEGER | The date the battery was manufactured UNIX Epoch |

### carbon_black_info

**Platforms:** MacOS Linux Windows

Returns info about a Carbon Black sensor install.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| sensor_id | INTEGER | Sensor ID of the Carbon Black sensor |
| config_name | TEXT | Sensor group |
| collect_store_files | INTEGER | If the sensor is configured to send back binaries to the Carbon Black server |
| collect_module_loads | INTEGER | If the sensor is configured to capture module loads |
| collect_module_info | INTEGER | If the sensor is configured to collect metadata of binaries |
| collect_file_mods | INTEGER | If the sensor is configured to collect file modification events |
| collect_reg_mods | INTEGER | If the sensor is configured to collect registry modification events |
| collect_net_conns | INTEGER | If the sensor is configured to collect network connections |
| collect_processes | INTEGER | If the sensor is configured to process events |
| collect_cross_processes | INTEGER | If the sensor is configured to cross process events |
| collect_emet_events | INTEGER | If the sensor is configured to EMET events |
| collect_data_file_writes | INTEGER | If the sensor is configured to collect non binary file writes |
| collect_process_user_context | INTEGER | If the sensor is configured to collect the user running a process |
| collect_sensor_operations | INTEGER | Unknown |
| log_file_disk_quota_mb | INTEGER | Event file disk quota in MB |
| log_file_disk_quota_percentage | INTEGER | Event file disk quota in a percentage |
| protection_disabled | INTEGER | If the sensor is configured to report tamper events |
| sensor_ip_addr | TEXT | IP address of the sensor |
| sensor_backend_server | TEXT | Carbon Black server |
| event_queue | INTEGER | Size in bytes of Carbon Black event files on disk |
| binary_queue | INTEGER | Size in bytes of binaries waiting to be sent to Carbon Black server |

### chassis_info

**Platforms:** Windows

Display information pertaining to the chassis and its security status.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| audible_alarm | TEXT | If TRUE, the frame is equipped with an audible alarm. |
| breach_description | TEXT | If provided, gives a more detailed description of a detected security breach. |
| chassis_types | TEXT | A comma-separated list of chassis types, such as Desktop or Laptop. |
| description | TEXT | An extended description of the chassis if available. |
| lock | TEXT | If TRUE, the frame is equipped with a lock. |
| manufacturer | TEXT | The manufacturer of the chassis. |
| model | TEXT | The model of the chassis. |
| security_breach | TEXT | The physical status of the chassis such as Breach Successful, Breach Attempted, etc. |
| serial | TEXT | The serial number of the chassis. |
| smbios_tag | TEXT | The assigned asset tag number of the chassis. |
| sku | TEXT | The Stock Keeping Unit number if available. |
| status | TEXT | If available, gives various operational or nonoperational statuses such as OK, Degraded, and Pred Fail. |
| visible_alarm | TEXT | If TRUE, the frame is equipped with a visual alarm. |

### connected_displays

**Platforms:** MacOS

Provides information about the connected displays of the machine.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | The name of the display. |
| product_id | TEXT | The product ID of the display. |
| serial_number | TEXT | The serial number of the display. (may not be unique) |
| vendor_id | TEXT | The vendor ID of the display. |
| manufactured_week | INTEGER | The manufacture week of the display. This field is 0 if not supported |
| manufactured_year | INTEGER | The manufacture year of the display. This field is 0 if not supported |
| display_id | TEXT | The display ID. |
| pixels | TEXT | The number of pixels of the display. |
| resolution | TEXT | The resolution of the display. |
| ambient_brightness_enabled | TEXT | The ambient brightness setting associated with the display. This will be 1 if enabled and is 0 if disabled or not supported. |
| connection_type | TEXT | The connection type associated with the display. |
| display_type | TEXT | The type of display. |
| main | INTEGER | If the display is the main display. |
| mirror | INTEGER | If the display is mirrored or not. This field is 1 if mirrored and 0 if not mirrored. |
| online | INTEGER | The online status of the display. This field is 1 if the display is online and 0 if it is offline. |
| rotation | TEXT | The rotation of the display (0, 90, 180, or 270 degrees). This field is -1 if display rotation is not supported. |

### cpu_info

**Platforms:** MacOS Linux Windows

Retrieve cpu hardware info of the machine.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| device_id | TEXT | The DeviceID of the CPU. |
| model | TEXT | The model of the CPU. |
| manufacturer | TEXT | The manufacturer of the CPU. |
| processor_type | TEXT | The processor type, such as Central, Math, or Video. |
| cpu_status | INTEGER | The current operating status of the CPU. |
| number_of_cores | TEXT | The number of cores of the CPU. |
| logical_processors | INTEGER | The number of logical processors of the CPU. |
| address_width | TEXT | The width of the CPU address bus. |
| current_clock_speed | INTEGER | The current frequency of the CPU. |
| max_clock_speed | INTEGER | The maximum possible frequency of the CPU. |
| socket_designation | TEXT | The assigned socket on the board for the given CPU. |
| availability | TEXT | The availability and status of the CPU. |
| load_percentage | INTEGER | The current percentage of utilization of the CPU. |
| number_of_efficiency_cores | INTEGER | The number of efficiency cores of the CPU. Only available on Apple Silicon |
| number_of_performance_cores | INTEGER | The number of performance cores of the CPU. Only available on Apple Silicon |

### cpu_time

**Platforms:** MacOS Linux

Displays information from /proc/stat file about the time the cpu cores spent in different parts of the system.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| core | INTEGER | Name of the cpu (core) |
| user | BIGINT | Time spent in user mode |
| nice | BIGINT | Time spent in user mode with low priority (nice) |
| system | BIGINT | Time spent in system mode |
| idle | BIGINT | Time spent in the idle task |
| iowait | BIGINT | Time spent waiting for I/O to complete |
| irq | BIGINT | Time spent servicing interrupts |
| softirq | BIGINT | Time spent servicing softirqs |
| steal | BIGINT | Time spent in other operating systems when running in a virtualized environment |
| guest | BIGINT | Time spent running a virtual CPU for a guest OS under the control of the Linux kernel |
| guest_nice | BIGINT | Time spent running a niced guest |

### cpuid

**Platforms:** MacOS Linux Windows

Useful CPU features from the cpuid ASM call.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| feature | TEXT | Present feature flags |
| value | TEXT | Bit value or string |
| output_register | TEXT | Register used to for feature value |
| output_bit | INTEGER | Bit in register value for feature value |
| input_eax | TEXT | Value of EAX used |

### crashes

**Platforms:** MacOS

Application, System, and Mobile App crash logs.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| type | TEXT | Type of crash log |
| pid | BIGINT | Process (or thread) ID of the crashed process |
| path | TEXT | Path to the crashed process |
| crash_path | TEXT | Location of log file |
| identifier | TEXT | Identifier of the crashed process |
| version | TEXT | Version info of the crashed process |
| parent | BIGINT | Parent PID of the crashed process |
| responsible | TEXT | Process responsible for the crashed process |
| uid | INTEGER | User ID of the crashed process |
| datetime | TEXT | Date/Time at which the crash occurred |
| crashed_thread | BIGINT | Thread ID which crashed |
| stack_trace | TEXT | Most recent frame from the stack trace |
| exception_type | TEXT | Exception type of the crash |
| exception_codes | TEXT | Exception codes from the crash |
| exception_notes | TEXT | Exception notes from the crash |
| registers | TEXT | The value of the system registers |

### crontab

**Platforms:** MacOS Linux

Line parsed values from system and user cron/tab.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| event | TEXT | The job @event name (rare) |
| minute | TEXT | The exact minute for the job |
| hour | TEXT | The hour of the day for the job |
| day_of_month | TEXT | The day of the month for the job |
| month | TEXT | The month of the year for the job |
| day_of_week | TEXT | The day of the week for the job |
| command | TEXT | Raw command string |
| path | TEXT | File parsed |
| pid_with_namespace | INTEGER | Pids that contain a namespace |

### device_firmware

**Platforms:** MacOS

A best-effort list of discovered firmware versions.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| type | TEXT | Type of device |
| device | TEXT | The device name |
| version | TEXT | Firmware version |

### fan_speed_sensors

**Platforms:** MacOS

Fan speeds.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| fan | TEXT | Fan number |
| name | TEXT | Fan name |
| actual | INTEGER | Actual speed |
| min | INTEGER | Minimum speed |
| max | INTEGER | Maximum speed |
| target | INTEGER | Target speed |

### hardware_events

**Platforms:** MacOS Linux

**Table Type:** EVENTED TABLE

Hardware (PCI/USB/HID) events from UDEV or IOKit.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| action | TEXT | Remove, insert, change properties, etc |
| path | TEXT | Local device path assigned (optional) |
| type | TEXT | Type of hardware and hardware event |
| driver | TEXT | Driver claiming the device |
| vendor | TEXT | Hardware device vendor |
| vendor_id | TEXT | Hex encoded Hardware vendor identifier |
| model | TEXT | Hardware device model |
| model_id | TEXT | Hex encoded Hardware model identifier |
| serial | TEXT | Device serial (optional) |
| revision | TEXT | Device revision (optional) |
| time | BIGINT | Time of hardware event |
| eid | TEXT | Event ID |

### ibridge_info

**Platforms:** MacOS

Information about the Apple iBridge hardware controller.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| boot_uuid | TEXT | Boot UUID of the iBridge controller |
| coprocessor_version | TEXT | The manufacturer and chip version |
| firmware_version | TEXT | The build version of the firmware |
| unique_chip_id | TEXT | Unique id of the iBridge controller |

### intel_me_info

**Platforms:** Linux Windows

Intel ME/CSE Info.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| version | TEXT | Intel ME version |

### iokit_devicetree

**Platforms:** MacOS

The IOKit registry matching the DeviceTree plane.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Device node name |
| class | TEXT | Best matching device class (most-specific category) |
| id | BIGINT | IOKit internal registry ID |
| parent | BIGINT | Parent device registry ID |
| device_path | TEXT | Device tree path |
| service | INTEGER | 1 if the device conforms to IOService else 0 |
| busy_state | INTEGER | 1 if the device is in a busy state else 0 |
| retain_count | INTEGER | The device reference count |
| depth | INTEGER | Device nested depth |

### iokit_registry

**Platforms:** MacOS

The full IOKit registry without selecting a plane.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Default name of the node |
| class | TEXT | Best matching device class (most-specific category) |
| id | BIGINT | IOKit internal registry ID |
| parent | BIGINT | Parent registry ID |
| busy_state | INTEGER | 1 if the node is in a busy state else 0 |
| retain_count | INTEGER | The node reference count |
| depth | INTEGER | Node nested depth |

### kernel_info

**Platforms:** MacOS Linux Windows

Basic active kernel information.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| version | TEXT | Kernel version |
| arguments | TEXT | Kernel arguments |
| path | TEXT | Kernel path |
| device | TEXT | Kernel device identifier |

### kernel_panics

**Platforms:** MacOS

System kernel panic logs.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| path | TEXT | Location of log file |
| time | TEXT | Formatted time of the event |
| registers | TEXT | A space delimited line of register:value pairs |
| frame_backtrace | TEXT | Backtrace of the crashed module |
| module_backtrace | TEXT | Modules appearing in the crashed module's backtrace |
| dependencies | TEXT | Module dependencies existing in crashed module's backtrace |
| name | TEXT | Process name corresponding to crashed thread |
| os_version | TEXT | Version of the operating system |
| kernel_version | TEXT | Version of the system kernel |
| system_model | TEXT | Physical system model, for example 'MacBookPro12,1 (Mac-E43C1C25D4880AD6)' |
| uptime | BIGINT | System uptime at kernel panic in nanoseconds |
| last_loaded | TEXT | Last loaded module before panic |
| last_unloaded | TEXT | Last unloaded module before panic |

### kva_speculative_info

**Platforms:** Windows

Display kernel virtual address and speculative execution information for the system.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| kva_shadow_enabled | INTEGER | Kernel Virtual Address shadowing is enabled. |
| kva_shadow_user_global | INTEGER | User pages are marked as global. |
| kva_shadow_pcid | INTEGER | Kernel VA PCID flushing optimization is enabled. |
| kva_shadow_inv_pcid | INTEGER | Kernel VA INVPCID is enabled. |
| bp_mitigations | INTEGER | Branch Prediction mitigations are enabled. |
| bp_system_pol_disabled | INTEGER | Branch Predictions are disabled via system policy. |
| bp_microcode_disabled | INTEGER | Branch Predictions are disabled due to lack of microcode update. |
| cpu_spec_ctrl_supported | INTEGER | SPEC_CTRL MSR supported by CPU Microcode. |
| ibrs_support_enabled | INTEGER | Windows uses IBRS. |
| stibp_support_enabled | INTEGER | Windows uses STIBP. |
| cpu_pred_cmd_supported | INTEGER | PRED_CMD MSR supported by CPU Microcode. |

### load_average

**Platforms:** MacOS Linux

Displays information about the system wide load averages.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| period | TEXT | Period over which the average is calculated. |
| average | TEXT | Load average over the specified period. |

### logical_drives

**Platforms:** Windows

Details for logical drives on the system. A logical drive generally represents a single partition.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| device_id | TEXT | The drive id, usually the drive name, e.g., 'C:'. |
| type | TEXT | Deprecated (always 'Unknown'). |
| description | TEXT | The canonical description of the drive, e.g. 'Logical Fixed Disk', 'CD-ROM Disk'. |
| free_space | BIGINT | The amount of free space, in bytes, of the drive (-1 on failure). |
| size | BIGINT | The total amount of space, in bytes, of the drive (-1 on failure). |
| file_system | TEXT | The file system of the drive. |
| boot_partition | INTEGER | True if Windows booted from this drive. |

### memory_array_mapped_addresses

**Platforms:** MacOS Linux

Data associated for address mapping of physical memory arrays.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| handle | TEXT | Handle, or instance number, associated with the structure |
| memory_array_handle | TEXT | Handle of the memory array associated with this structure |
| starting_address | TEXT | Physical stating address, in kilobytes, of a range of memory mapped to physical memory array |
| ending_address | TEXT | Physical ending address of last kilobyte of a range of memory mapped to physical memory array |
| partition_width | INTEGER | Number of memory devices that form a single row of memory for the address partition of this structure |

### memory_arrays

**Platforms:** MacOS Linux

Data associated with collection of memory devices that operate to form a memory address.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| handle | TEXT | Handle, or instance number, associated with the array |
| location | TEXT | Physical location of the memory array |
| use | TEXT | Function for which the array is used |
| memory_error_correction | TEXT | Primary hardware error correction or detection method supported |
| max_capacity | INTEGER | Maximum capacity of array in gigabytes |
| memory_error_info_handle | TEXT | Handle, or instance number, associated with any error that was detected for the array |
| number_memory_devices | INTEGER | Number of memory devices on array |

### memory_device_mapped_addresses

**Platforms:** MacOS Linux

Data associated for address mapping of physical memory devices.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| handle | TEXT | Handle, or instance number, associated with the structure |
| memory_device_handle | TEXT | Handle of the memory device structure associated with this structure |
| memory_array_mapped_address_handle | TEXT | Handle of the memory array mapped address to which this device range is mapped to |
| starting_address | TEXT | Physical stating address, in kilobytes, of a range of memory mapped to physical memory array |
| ending_address | TEXT | Physical ending address of last kilobyte of a range of memory mapped to physical memory array |
| partition_row_position | INTEGER | Identifies the position of the referenced memory device in a row of the address partition |
| interleave_position | INTEGER | The position of the device in a interleave, i.e. 0 indicates non-interleave, 1 indicates 1st interleave, 2 indicates 2nd interleave, etc. |
| interleave_data_depth | INTEGER | The max number of consecutive rows from memory device that are accessed in a single interleave transfer; 0 indicates device is non-interleave |

### memory_devices

**Platforms:** MacOS Linux Windows

Physical memory device (type 17) information retrieved from SMBIOS.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| handle | TEXT | Handle, or instance number, associated with the structure in SMBIOS |
| array_handle | TEXT | The memory array that the device is attached to |
| form_factor | TEXT | Implementation form factor for this memory device |
| total_width | INTEGER | Total width, in bits, of this memory device, including any check or error-correction bits |
| data_width | INTEGER | Data width, in bits, of this memory device |
| size | INTEGER | Size of memory device in Megabyte |
| set | INTEGER | Identifies if memory device is one of a set of devices. A value of 0 indicates no set affiliation. |
| device_locator | TEXT | String number of the string that identifies the physically-labeled socket or board position where the memory device is located |
| bank_locator | TEXT | String number of the string that identifies the physically-labeled bank where the memory device is located |
| memory_type | TEXT | Type of memory used |
| memory_type_details | TEXT | Additional details for memory device |
| max_speed | INTEGER | Max speed of memory device in megatransfers per second (MT/s) |
| configured_clock_speed | INTEGER | Configured speed of memory device in megatransfers per second (MT/s) |
| manufacturer | TEXT | Manufacturer ID string |
| serial_number | TEXT | Serial number of memory device |
| asset_tag | TEXT | Manufacturer specific asset tag of memory device |
| part_number | TEXT | Manufacturer specific serial number of memory device |
| min_voltage | INTEGER | Minimum operating voltage of device in millivolts |
| max_voltage | INTEGER | Maximum operating voltage of device in millivolts |
| configured_voltage | INTEGER | Configured operating voltage of device in millivolts |

### memory_error_info

**Platforms:** MacOS Linux

Data associated with errors of a physical memory array.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| handle | TEXT | Handle, or instance number, associated with the structure |
| error_type | TEXT | type of error associated with current error status for array or device |
| error_granularity | TEXT | Granularity to which the error can be resolved |
| error_operation | TEXT | Memory access operation that caused the error |
| vendor_syndrome | TEXT | Vendor specific ECC syndrome or CRC data associated with the erroneous access |
| memory_array_error_address | TEXT | 32 bit physical address of the error based on the addressing of the bus to which the memory array is connected |
| device_error_address | TEXT | 32 bit physical address of the error relative to the start of the failing memory address, in bytes |
| error_resolution | TEXT | Range, in bytes, within which this error can be determined, when an error address is given |

### memory_info

**Platforms:** Linux

Main memory information in bytes.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| memory_total | BIGINT | Total amount of physical RAM, in bytes |
| memory_free | BIGINT | The amount of physical RAM, in bytes, left unused by the system |
| memory_available | BIGINT | The amount of physical RAM, in bytes, available for starting new applications, without swapping |
| buffers | BIGINT | The amount of physical RAM, in bytes, used for file buffers |
| cached | BIGINT | The amount of physical RAM, in bytes, used as cache memory |
| swap_cached | BIGINT | The amount of swap, in bytes, used as cache memory |
| active | BIGINT | The total amount of buffer or page cache memory, in bytes, that is in active use |
| inactive | BIGINT | The total amount of buffer or page cache memory, in bytes, that are free and available |
| swap_total | BIGINT | The total amount of swap available, in bytes |
| swap_free | BIGINT | The total amount of swap free, in bytes |

### memory_map

**Platforms:** Linux

OS memory region map.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Region name |
| start | TEXT | Start address of memory region |
| end | TEXT | End address of memory region |

### msr

**Platforms:** Linux

Various pieces of data stored in the model specific register per processor. NOTE: the msr kernel module must be enabled, and osquery must be run as root.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| processor_number | BIGINT | The processor number as reported in /proc/cpuinfo |
| turbo_disabled | BIGINT | Whether the turbo feature is disabled. |
| turbo_ratio_limit | BIGINT | The turbo feature ratio limit. |
| platform_info | BIGINT | Platform information. |
| perf_ctl | BIGINT | Performance setting for the processor. |
| perf_status | BIGINT | Performance status for the processor. |
| feature_control | BIGINT | Bitfield controlling enabled features. |
| rapl_power_limit | BIGINT | Run Time Average Power Limiting power limit. |
| rapl_energy_status | BIGINT | Run Time Average Power Limiting energy status. |
| rapl_power_units | BIGINT | Run Time Average Power Limiting power units. |

### nvram

**Platforms:** MacOS

Apple NVRAM variable listing.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Variable name |
| type | TEXT | Data type (CFData, CFString, etc) |
| value | TEXT | Raw variable data |

### oem_strings

**Platforms:** MacOS Linux

OEM defined strings retrieved from SMBIOS.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| handle | TEXT | Handle, or instance number, associated with the Type 11 structure |
| number | INTEGER | The string index of the structure |
| value | TEXT | The value of the OEM string |

### os_version

**Platforms:** MacOS Linux Windows

A single row containing the operating system name and version.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Distribution or product name |
| version | TEXT | Pretty, suitable for presentation, OS version |
| major | INTEGER | Major release version |
| minor | INTEGER | Minor release version |
| patch | INTEGER | Optional patch release |
| build | TEXT | Optional build-specific or variant string |
| platform | TEXT | OS Platform or ID |
| platform_like | TEXT | Closely related platforms |
| codename | TEXT | OS version codename |
| arch | TEXT | OS Architecture |
| extra | TEXT | Optional extra release specification |
| install_date | BIGINT | The install date of the OS. |
| revision | INTEGER | Update Build Revision, refers to the specific revision number of a Windows update |
| pid_with_namespace | INTEGER | Pids that contain a namespace |
| mount_namespace_id | TEXT | Mount namespace id |

### pci_devices

**Platforms:** MacOS Linux

PCI devices active on the host system.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| pci_slot | TEXT | PCI Device used slot |
| pci_class | TEXT | PCI Device class |
| driver | TEXT | PCI Device used driver |
| vendor | TEXT | PCI Device vendor |
| vendor_id | TEXT | Hex encoded PCI Device vendor identifier |
| model | TEXT | PCI Device model |
| model_id | TEXT | Hex encoded PCI Device model identifier |
| pci_class_id | TEXT | PCI Device class ID in hex format |
| pci_subclass_id | TEXT | PCI Device subclass in hex format |
| pci_subclass | TEXT | PCI Device subclass |
| subsystem_vendor_id | TEXT | Vendor ID of PCI device subsystem |
| subsystem_vendor | TEXT | Vendor of PCI device subsystem |
| subsystem_model_id | TEXT | Model ID of PCI device subsystem |
| subsystem_model | TEXT | Device description of PCI device subsystem |

### physical_disk_performance

**Platforms:** Windows

Provides provides raw data from performance counters that monitor hard or fixed disk drives on the system.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Name of the physical disk |
| avg_disk_bytes_per_read | BIGINT | Average number of bytes transferred from the disk during read operations |
| avg_disk_bytes_per_write | BIGINT | Average number of bytes transferred to the disk during write operations |
| avg_disk_read_queue_length | BIGINT | Average number of read requests that were queued for the selected disk during the sample interval |
| avg_disk_write_queue_length | BIGINT | Average number of write requests that were queued for the selected disk during the sample interval |
| avg_disk_sec_per_read | INTEGER | Average time, in seconds, of a read operation of data from the disk |
| avg_disk_sec_per_write | INTEGER | Average time, in seconds, of a write operation of data to the disk |
| current_disk_queue_length | INTEGER | Number of requests outstanding on the disk at the time the performance data is collected |
| percent_disk_read_time | BIGINT | Percentage of elapsed time that the selected disk drive is busy servicing read requests |
| percent_disk_write_time | BIGINT | Percentage of elapsed time that the selected disk drive is busy servicing write requests |
| percent_disk_time | BIGINT | Percentage of elapsed time that the selected disk drive is busy servicing read or write requests |
| percent_idle_time | BIGINT | Percentage of time during the sample interval that the disk was idle |

### platform_info

**Platforms:** MacOS Linux Windows

Information about EFI/UEFI/ROM and platform/boot.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| vendor | TEXT | Platform code vendor |
| version | TEXT | Platform code version |
| date | TEXT | Self-reported platform code update date |
| revision | TEXT | BIOS major and minor revision |
| extra | TEXT | Platform-specific additional information |
| firmware_type | TEXT | The type of firmware (uefi, bios, iboot, openfirmware, unknown). |
| address | TEXT | Relative address of firmware mapping |
| size | TEXT | Size in bytes of firmware |
| volume_size | INTEGER | (Optional) size of firmware volume |

### power_sensors

**Platforms:** MacOS

Machine power (currents, voltages, wattages, etc) sensors.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| key | TEXT | The SMC key on macOS |
| category | TEXT | The sensor category: currents, voltage, wattage |
| name | TEXT | Name of power source |
| value | TEXT | Power in Watts |

### registry

**Platforms:** Windows

All of the Windows registry hives.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| key | TEXT | Name of the key to search for |
| path | TEXT | Full path to the value |
| name | TEXT | Name of the registry value entry |
| type | TEXT | Type of the registry value, or 'subkey' if item is a subkey |
| data | TEXT | Data content of registry value |
| mtime | BIGINT | timestamp of the most recent registry write |

### secureboot

**Platforms:** MacOS Linux Windows

Secure Boot UEFI Settings.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| secure_boot | INTEGER | Whether secure boot is enabled |
| secure_mode | INTEGER | (Intel) Secure mode: 0 disabled, 1 full security, 2 medium security |
| description | TEXT | (Apple Silicon) Human-readable description: 'Full Security', 'Reduced Security', or 'Permissive Security' |
| kernel_extensions | INTEGER | (Apple Silicon) Allow user management of kernel extensions from identified developers (1 if allowed) |
| mdm_operations | INTEGER | (Apple Silicon) Allow remote (MDM) management of kernel extensions and automatic software updates (1 if allowed) |
| setup_mode | INTEGER | Whether setup mode is enabled |

### secureboot_certificates

**Platforms:** Linux

**Status:** New

X.509 certificates from UEFI Secure Boot signature databases (db and dbx EFI variables). Useful for monitoring CA expiry and adoption of updated certificates (e.g. Microsoft UEFI CA 2023).

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| common_name | TEXT | Certificate CommonName |
| subject | TEXT | Certificate subject distinguished name |
| issuer | TEXT | Certificate issuer distinguished name |
| not_valid_before | TEXT | Lower bound of valid date |
| not_valid_after | TEXT | Certificate expiration date |
| sha1 | TEXT | SHA1 hash of the raw certificate contents |
| serial | TEXT | Certificate serial number |
| revoked | INTEGER | 1 if the certificate is in the dbx revocation list, 0 if it is in the db allowlist |
| path | TEXT | Path to the EFI variable file |
| is_ca | INTEGER | 1 if the certificate is a CA, 0 otherwise |
| self_signed | INTEGER | 1 if the certificate is self-signed, 0 otherwise |
| key_usage | TEXT | Certificate key usage extension string |
| authority_key_id | TEXT | Authority Key Identifier (AKI) |
| subject_key_id | TEXT | Subject Key Identifier (SKI) |
| signing_algorithm | TEXT | Algorithm used to sign the certificate |
| key_algorithm | TEXT | Public key algorithm |
| key_strength | TEXT | Public key size in bits |

### smc_keys

**Platforms:** MacOS

Apple's system management controller keys.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| key | TEXT | 4-character key |
| type | TEXT | SMC-reported type literal type |
| size | INTEGER | Reported size of data in bytes |
| value | TEXT | A type-encoded representation of the key value |
| hidden | INTEGER | 1 if this key is normally hidden, otherwise 0 |

### suid_bin

**Platforms:** MacOS Linux

suid binaries in common locations.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| path | TEXT | Binary path |
| username | TEXT | Binary owner username |
| groupname | TEXT | Binary owner group |
| permissions | TEXT | Binary permissions |
| pid_with_namespace | INTEGER | Pids that contain a namespace |

### system_controls

**Platforms:** MacOS Linux

sysctl names, values, and settings information.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Full sysctl MIB name |
| oid | TEXT | Control MIB |
| subsystem | TEXT | Subsystem ID, control type |
| current_value | TEXT | Value of setting |
| config_value | TEXT | The MIB value set in /etc/sysctl.conf |
| type | TEXT | Data type |
| field_name | TEXT | Specific attribute of opaque type |

### system_info

**Platforms:** MacOS Linux Windows

System information for identification.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| hostname | TEXT | Network hostname including domain |
| uuid | TEXT | Unique ID provided by the system |
| cpu_type | TEXT | CPU type |
| cpu_subtype | TEXT | CPU subtype |
| cpu_brand | TEXT | CPU brand string, contains vendor and model |
| cpu_physical_cores | INTEGER | Number of physical CPU cores in to the system |
| cpu_logical_cores | INTEGER | Number of logical CPU cores available to the system |
| cpu_sockets | INTEGER | Number of processor sockets in the system |
| cpu_microcode | TEXT | Microcode version |
| physical_memory | BIGINT | Total physical memory in bytes |
| hardware_vendor | TEXT | Hardware vendor |
| hardware_model | TEXT | Hardware model |
| hardware_version | TEXT | Hardware version |
| hardware_serial | TEXT | Device serial number |
| board_vendor | TEXT | Board vendor |
| board_model | TEXT | Board model |
| board_version | TEXT | Board version |
| board_serial | TEXT | Board serial number |
| computer_name | TEXT | Friendly computer name (optional) |
| local_hostname | TEXT | Local hostname (optional) |
| emulated_cpu_type | TEXT | Emulated CPU type |

### system_profiler

**Platforms:** MacOS

Query system_profiler data types and return the full result as JSON. Returns only the data types specified in the constraints. See available data types with `system_profiler -listDataTypes`.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| data_type | TEXT | The system profiler data type (e.g., SPHardwareDataType) Required in WHERE clause |
| value | TEXT | A JSON representation of the full result dictionary for the data type |

### temperature_sensors

**Platforms:** MacOS

Machine's temperature sensors.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| key | TEXT | The SMC key on macOS |
| name | TEXT | Name of temperature source |
| celsius | DOUBLE | Temperature in Celsius |
| fahrenheit | DOUBLE | Temperature in Fahrenheit |

### time

**Platforms:** MacOS Linux Windows

Track current date and time in UTC.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| weekday | TEXT | Current weekday in UTC |
| year | INTEGER | Current year in UTC |
| month | INTEGER | Current month in UTC |
| day | INTEGER | Current day in UTC |
| hour | INTEGER | Current hour in UTC |
| minutes | INTEGER | Current minutes in UTC |
| seconds | INTEGER | Current seconds in UTC |
| timezone | TEXT | Timezone for reported time (hardcoded to UTC) |
| local_timezone | TEXT | Current local timezone in of the system |
| unix_time | INTEGER | Current UNIX time in UTC |
| timestamp | TEXT | Current timestamp (log format) in UTC |
| datetime | TEXT | Current date and time (ISO format) in UTC |
| iso_8601 | TEXT | Current time (ISO format) in UTC |
| win_timestamp | BIGINT | Timestamp value in 100 nanosecond units |

### time_machine_backups

**Platforms:** MacOS

Backups to drives using TimeMachine. This table requires Full Disk Access (FDA) permission.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| destination_id | TEXT | Time Machine destination ID |
| backup_date | INTEGER | Backup Date |

### time_machine_destinations

**Platforms:** MacOS

Locations backed up to using Time Machine. This table requires Full Disk Access (FDA) permission.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| alias | TEXT | Human readable name of drive |
| destination_id | TEXT | Time Machine destination ID |
| consistency_scan_date | INTEGER | Consistency scan date |
| root_volume_uuid | TEXT | Root UUID of backup volume |
| bytes_available | INTEGER | Bytes available on volume |
| bytes_used | INTEGER | Bytes used on volume |
| encryption | TEXT | Last known encrypted state |

### tpm_info

**Platforms:** Windows

A table that lists the TPM related information.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| activated | INTEGER | TPM is activated |
| enabled | INTEGER | TPM is enabled |
| owned | INTEGER | TPM is owned |
| manufacturer_version | TEXT | TPM version |
| manufacturer_id | INTEGER | TPM manufacturers ID |
| manufacturer_name | TEXT | TPM manufacturers name |
| product_name | TEXT | Product name of the TPM |
| physical_presence_version | TEXT | Version of the Physical Presence Interface |
| spec_version | TEXT | Trusted Computing Group specification that the TPM supports |

### ulimit_info

**Platforms:** MacOS Linux

System resource usage limits.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| type | TEXT | System resource to be limited |
| soft_limit | TEXT | Current limit value |
| hard_limit | TEXT | Maximum limit value |

### uptime

**Platforms:** MacOS Linux Windows

Track time passed since last boot. Some systems track this as calendar time, some as runtime.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| days | INTEGER | Days of uptime |
| hours | INTEGER | Hours of uptime |
| minutes | INTEGER | Minutes of uptime |
| seconds | INTEGER | Seconds of uptime |
| total_seconds | BIGINT | Total uptime seconds |

### usb_devices

**Platforms:** MacOS Linux

USB devices that are actively plugged into the host system.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| usb_address | INTEGER | USB Device used address |
| usb_port | INTEGER | USB Device used port |
| vendor | TEXT | USB Device vendor string |
| vendor_id | TEXT | Hex encoded USB Device vendor identifier |
| version | TEXT | USB Device version number |
| model | TEXT | USB Device model string |
| model_id | TEXT | Hex encoded USB Device model identifier |
| serial | TEXT | USB Device serial connection |
| class | TEXT | USB Device class |
| subclass | TEXT | USB Device subclass |
| protocol | TEXT | USB Device protocol |
| removable | INTEGER | 1 If USB device is removable else 0 |

### video_info

**Platforms:** Windows

Retrieve video card information of the machine.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| color_depth | INTEGER | The amount of bits per pixel to represent color. |
| driver | TEXT | The driver of the device. |
| driver_date | BIGINT | The date listed on the installed driver. |
| driver_version | TEXT | The version of the installed driver. |
| manufacturer | TEXT | The manufacturer of the gpu. |
| model | TEXT | The model of the gpu. |
| series | TEXT | The series of the gpu. |
| video_mode | TEXT | The current resolution of the display. |

### virtual_memory_info

**Platforms:** MacOS

Darwin Virtual Memory statistics.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| free | BIGINT | Total number of free pages. |
| active | BIGINT | Total number of active pages. |
| inactive | BIGINT | Total number of inactive pages. |
| speculative | BIGINT | Total number of speculative pages. |
| throttled | BIGINT | Total number of throttled pages. |
| wired | BIGINT | Total number of wired down pages. |
| purgeable | BIGINT | Total number of purgeable pages. |
| faults | BIGINT | Total number of calls to vm_faults. |
| copy | BIGINT | Total number of copy-on-write pages. |
| zero_fill | BIGINT | Total number of zero filled pages. |
| reactivated | BIGINT | Total number of reactivated pages. |
| purged | BIGINT | Total number of purged pages. |
| file_backed | BIGINT | Total number of file backed pages. |
| anonymous | BIGINT | Total number of anonymous pages. |
| uncompressed | BIGINT | Total number of uncompressed pages. |
| compressor | BIGINT | The number of pages used to store compressed VM pages. |
| decompressed | BIGINT | The total number of pages that have been decompressed by the VM compressor. |
| compressed | BIGINT | The total number of pages that have been compressed by the VM compressor. |
| page_ins | BIGINT | The total number of requests for pages from a pager. |
| page_outs | BIGINT | Total number of pages paged out. |
| swap_ins | BIGINT | The total number of compressed pages that have been swapped out to disk. |
| swap_outs | BIGINT | The total number of compressed pages that have been swapped back in from disk. |

### windows_crashes

**Platforms:** Windows

Extracted information from Windows crash logs (Minidumps).

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| datetime | TEXT | Timestamp (log format) of the crash |
| module | TEXT | Path of the crashed module within the process |
| path | TEXT | Path of the executable file for the crashed process |
| pid | BIGINT | Process ID of the crashed process |
| tid | BIGINT | Thread ID of the crashed thread |
| version | TEXT | File version info of the crashed process |
| process_uptime | BIGINT | Uptime of the process in seconds |
| stack_trace | TEXT | Multiple stack frames from the stack trace |
| exception_code | TEXT | The Windows exception code |
| exception_message | TEXT | The NTSTATUS error message associated with the exception code |
| exception_address | TEXT | Address (in hex) where the exception occurred |
| registers | TEXT | The values of the system registers |
| command_line | TEXT | Command-line string passed to the crashed process |
| current_directory | TEXT | Current working directory of the crashed process |
| username | TEXT | Username of the user who ran the crashed process |
| machine_name | TEXT | Name of the machine where the crash happened |
| major_version | INTEGER | Windows major version of the machine |
| minor_version | INTEGER | Windows minor version of the machine |
| build_number | INTEGER | Windows build number of the crashing machine |
| type | TEXT | Type of crash log |
| crash_path | TEXT | Path of the log file |

### wmi_bios_info

**Platforms:** Windows

Lists important information from the system bios.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Name of the Bios setting |
| value | TEXT | Value of the Bios setting |

<!-- DCOIR_SOURCE_END {"id":"knowledge.reference.osquery_system","sha256":"675e8fc0dfea1cedde605daf06537db132b12e1943f16f5e08cd36d04737670d"} -->

<!-- DCOIR_SOURCE_BEGIN {"bytes":16764,"git_blob_sha":"986a8180bdbb9cbb9ab2fc872cf21057ce641279","id":"knowledge.reference.osquery_users","path":"knowledge/Knowledge - Reference - OSQuery User, Auth, and Account Tables.md","sha256":"e90de964dc00df6fdf1dbfc29c3d02517204b4e56771dd2c72dab58f23aac68d"} -->
# Knowledge - Reference - OSQuery User, Auth, and Account Tables

_Exact OSQuery user, account, login, SSH, and auth-policy reference tables._

**Summary:** This page preserves the exact OSQuery source markdown for the tables in this shard. Use it as the governed exact-name reference for table and field lookup.

---

### account_policy_data

**Platforms:** MacOS

Additional macOS user account data from the AccountPolicy section of OpenDirectory.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| uid | BIGINT | User ID |
| creation_time | DOUBLE | When the account was first created |
| failed_login_count | BIGINT | The number of failed login attempts using an incorrect password. Count resets after a correct password is entered. |
| failed_login_timestamp | DOUBLE | The time of the last failed login attempt. Resets after a correct password is entered |
| password_last_set_time | DOUBLE | The time the password was last changed |

### ad_config

**Platforms:** MacOS

macOS Active Directory configuration.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | The macOS-specific configuration name |
| domain | TEXT | Active Directory trust domain |
| option | TEXT | Canonical name of option |
| value | TEXT | Variable typed option value |

### authorization_mechanisms

**Platforms:** MacOS

macOS Authorization mechanisms database.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| label | TEXT | Label of the authorization right |
| plugin | TEXT | Authorization plugin name |
| mechanism | TEXT | Name of the mechanism that will be called |
| privileged | TEXT | If privileged it will run as root, else as an anonymous user |
| entry | TEXT | The whole string entry |

### authorizations

**Platforms:** MacOS

macOS Authorization rights database.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| label | TEXT | Item name, usually in reverse domain format |
| modified | TEXT | Label top-level key |
| allow_root | TEXT | Label top-level key |
| timeout | TEXT | Label top-level key |
| version | TEXT | Label top-level key |
| tries | TEXT | Label top-level key |
| authenticate_user | TEXT | Label top-level key |
| shared | TEXT | Label top-level key |
| comment | TEXT | Label top-level key |
| created | TEXT | Label top-level key |
| class | TEXT | Label top-level key |
| session_owner | TEXT | Label top-level key |

### authorized_keys

**Platforms:** MacOS Linux

A line-delimited authorized_keys table.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| uid | BIGINT | The local owner of authorized_keys file |
| algorithm | TEXT | Key type |
| key | TEXT | Key encoded as base64 |
| options | TEXT | Optional list of login options |
| comment | TEXT | Optional comment |
| key_file | TEXT | Path to the authorized_keys file |
| pid_with_namespace | INTEGER | Pids that contain a namespace |

### default_environment

**Platforms:** Windows

Default environment variables and values.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| variable | TEXT | Name of the environment variable |
| value | TEXT | Value of the environment variable |
| expand | INTEGER | 1 if the variable needs expanding, 0 otherwise |

### groups

**Platforms:** MacOS Linux Windows

Local system groups.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| gid | BIGINT | Unsigned int64 group ID |
| gid_signed | BIGINT | A signed int64 version of gid |
| groupname | TEXT | Canonical local group name |
| group_sid | TEXT | Unique group ID |
| comment | TEXT | Remarks or comments associated with the group |
| is_hidden | INTEGER | IsHidden attribute set in OpenDirectory |
| pid_with_namespace | INTEGER | Pids that contain a namespace |

### known_hosts

**Platforms:** MacOS Linux

A line-delimited known_hosts table.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| uid | BIGINT | The local user that owns the known_hosts file |
| key | TEXT | parsed authorized keys line |
| key_file | TEXT | Path to known_hosts file |

### last

**Platforms:** MacOS Linux

System logins and logouts.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| username | TEXT | Entry username |
| tty | TEXT | Entry terminal |
| pid | INTEGER | Process (or thread) ID |
| type | INTEGER | Entry type, according to ut_type types (utmp.h) |
| type_name | TEXT | Entry type name, according to ut_type types (utmp.h) |
| time | INTEGER | Entry timestamp |
| host | TEXT | Entry hostname |

### location_services

**Platforms:** MacOS

Reports the status of the Location Services feature of the OS.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| enabled | INTEGER | 1 if Location Services are enabled, else 0 |

### logged_in_users

**Platforms:** MacOS Linux Windows

Users with an active shell on the system.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| type | TEXT | Login type |
| user | TEXT | User login name |
| tty | TEXT | Device name |
| host | TEXT | Remote hostname |
| time | BIGINT | Time entry was made |
| pid | INTEGER | Process (or thread) ID |
| sid | TEXT | The user's unique security identifier |
| registry_hive | TEXT | HKEY_USERS registry hive |

### logon_sessions

**Platforms:** Windows

Windows Logon Session.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| logon_id | INTEGER | A locally unique identifier (LUID) that identifies a logon session. |
| user | TEXT | The account name of the security principal that owns the logon session. |
| logon_domain | TEXT | The name of the domain used to authenticate the owner of the logon session. |
| authentication_package | TEXT | The authentication package used to authenticate the owner of the logon session. |
| logon_type | TEXT | The logon method. |
| session_id | INTEGER | The Terminal Services session identifier. |
| logon_sid | TEXT | The user's security identifier (SID). |
| logon_time | BIGINT | The time the session owner logged on. |
| logon_server | TEXT | The name of the server used to authenticate the owner of the logon session. |
| dns_domain_name | TEXT | The DNS name for the owner of the logon session. |
| upn | TEXT | The user principal name (UPN) for the owner of the logon session. |
| logon_script | TEXT | The script used for logging on. |
| profile_path | TEXT | The home directory for the logon session. |
| home_directory | TEXT | The home directory for the logon session. |
| home_directory_drive | TEXT | The drive location of the home directory of the logon session. |

### managed_policies

**Platforms:** MacOS

The managed configuration policies from AD, MDM, MCX, etc.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| domain | TEXT | System or manager-chosen domain key |
| uuid | TEXT | Optional UUID assigned to policy set |
| name | TEXT | Policy key name |
| value | TEXT | Policy value |
| username | TEXT | Policy applies only this user |
| manual | INTEGER | 1 if policy was loaded manually, otherwise 0 |

### ntdomains

**Platforms:** Windows

Display basic NT domain information of a Windows machine.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | The label by which the object is known. |
| client_site_name | TEXT | The name of the site where the domain controller is configured. |
| dc_site_name | TEXT | The name of the site where the domain controller is located. |
| dns_forest_name | TEXT | The name of the root of the DNS tree. |
| domain_controller_address | TEXT | The IP Address of the discovered domain controller.. |
| domain_controller_name | TEXT | The name of the discovered domain controller. |
| domain_name | TEXT | The name of the domain. |
| status | TEXT | The current status of the domain object. |

### office_mru

**Platforms:** Windows

View recently opened Office documents.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| application | TEXT | Associated Office application |
| version | TEXT | Office application version number |
| path | TEXT | File path |
| last_opened_time | BIGINT | Most recent opened time file was opened |
| sid | TEXT | User SID |

### password_policy

**Platforms:** MacOS

OpenDirectory account policies for macOS including password content, authentication, and password change policies.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| uid | BIGINT | User ID for the policy, -1 for policies that are global |
| policy_identifier | TEXT | Policy Identifier |
| policy_content | TEXT | Policy content |
| policy_description | TEXT | Policy description |
| policy_category | TEXT | Policy category: passwordPolicyAuthentication, passwordPolicyPasswordChange, or passwordPolicyPasswordContent |
| policy_parameters | TEXT | Policy parameters serialized as JSON |

### preferences

**Platforms:** MacOS

macOS defaults and managed preferences.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| domain | TEXT | Application ID usually in com.name.product format |
| key | TEXT | Preference top-level key |
| subkey | TEXT | Intemediate key path, includes lists/dicts |
| value | TEXT | String value of most CF types |
| forced | INTEGER | 1 if the value is forced/managed, else 0 |
| username | TEXT | (optional) read preferences for a specific user |
| host | TEXT | 'current' or 'any' host, where 'current' takes precedence |

### screenlock

**Platforms:** MacOS

macOS screenlock status. Note: only fetches results for osquery's current logged-in user context. The user must also have recently logged in.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| enabled | INTEGER | 1 If a password is required after sleep or the screensaver begins; else 0 |
| grace_period | INTEGER | The amount of time in seconds the screen must be asleep or the screensaver on before a password is required on-wake. 0 = immediately; -1 = no password is required on-wake |

### shadow

**Platforms:** Linux

Local system users encrypted passwords and related information. Please note, that you usually need superuser rights to access `/etc/shadow`.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| password_status | TEXT | Password status |
| hash_alg | TEXT | Password hashing algorithm |
| last_change | BIGINT | Date of last password change (starting from UNIX epoch date) |
| min | BIGINT | Minimal number of days between password changes |
| max | BIGINT | Maximum number of days between password changes |
| warning | BIGINT | Number of days before password expires to warn user about it |
| inactive | BIGINT | Number of days after password expires until account is blocked |
| expire | BIGINT | Number of days since UNIX epoch date until account is disabled |
| flag | BIGINT | Reserved |
| username | TEXT | Username |

### shared_folders

**Platforms:** MacOS

Folders available to others via SMB or AFP.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | The shared name of the folder as it appears to other users |
| path | TEXT | Absolute path of shared folder on the local system |

### sharing_preferences

**Platforms:** MacOS

macOS Sharing preferences.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| screen_sharing | INTEGER | 1 If screen sharing is enabled else 0 |
| file_sharing | INTEGER | 1 If file sharing is enabled else 0 |
| printer_sharing | INTEGER | 1 If printer sharing is enabled else 0 |
| remote_login | INTEGER | 1 If remote login is enabled else 0 |
| remote_management | INTEGER | 1 If remote management is enabled else 0 |
| remote_apple_events | INTEGER | 1 If remote apple events are enabled else 0 |
| internet_sharing | INTEGER | 1 If internet sharing is enabled else 0 |
| bluetooth_sharing | INTEGER | 1 If bluetooth sharing is enabled for any user else 0 |
| disc_sharing | INTEGER | 1 If CD or DVD sharing is enabled else 0 |
| content_caching | INTEGER | 1 If content caching is enabled else 0 |

### shell_history

**Platforms:** MacOS Linux

A line-delimited (command) table of per-user .*_history data.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| uid | BIGINT | Shell history owner |
| time | INTEGER | Entry timestamp. It could be absent, default value is 0. |
| command | TEXT | Unparsed date/line/command history line |
| history_file | TEXT | Path to the .*_history for this user |

### shellbags

**Platforms:** Windows

Shows directories accessed via Windows Explorer.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| sid | TEXT | User SID |
| source | TEXT | Shellbags source Registry file |
| path | TEXT | Directory name. |
| modified_time | BIGINT | Directory Modified time. |
| created_time | BIGINT | Directory Created time. |
| accessed_time | BIGINT | Directory Accessed time. |
| mft_entry | BIGINT | Directory master file table entry. |
| mft_sequence | INTEGER | Directory master file table sequence. |

### ssh_configs

**Platforms:** MacOS Linux Windows

A table of parsed ssh_configs.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| uid | BIGINT | The local owner of the ssh_config file |
| block | TEXT | The host or match block |
| option | TEXT | The option and value |
| ssh_config_file | TEXT | Path to the ssh_config file |

### sudoers

**Platforms:** MacOS Linux

Rules for running commands as other users via sudo.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| source | TEXT | Source file containing the given rule |
| header | TEXT | Symbol for given rule |
| rule_details | TEXT | Rule definition |

### user_groups

**Platforms:** MacOS Linux Windows

Local system user group relationships.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| uid | BIGINT | User ID |
| gid | BIGINT | Group ID |

### user_ssh_keys

**Platforms:** MacOS Linux Windows

Returns the private keys in the users ~/.ssh directory and whether or not they are encrypted.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| uid | BIGINT | The local user that owns the key file |
| path | TEXT | Path to key file |
| encrypted | INTEGER | 1 if key is encrypted, 0 otherwise |
| key_type | TEXT | The type of the private key. One of [rsa, dsa, dh, ec, hmac, cmac], or the empty string. |
| key_group_name | TEXT | The group of the private key. Supported for a subset of key_types implemented by OpenSSL |
| key_length | INTEGER | The cryptographic length of the cryptosystem to which the private key belongs, in bits. Definition of cryptographic length is specific to cryptosystem. -1 if unavailable |
| key_security_bits | INTEGER | The number of security bits of the private key, bits of security as defined in NIST SP800-57. -1 if unavailable |
| pid_with_namespace | INTEGER | Pids that contain a namespace |

### userassist

**Platforms:** Windows

UserAssist Registry Key tracks when a user executes an application from Windows Explorer.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| path | TEXT | Application file path. |
| last_execution_time | BIGINT | Most recent time application was executed. |
| count | INTEGER | Number of times the application has been executed. |
| sid | TEXT | User SID. |

### users

**Platforms:** MacOS Linux Windows

Local user accounts (including domain accounts that have logged on locally (Windows)).

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| uid | BIGINT | User ID |
| gid | BIGINT | Group ID (unsigned) |
| uid_signed | BIGINT | User ID as int64 signed (Apple) |
| gid_signed | BIGINT | Default group ID as int64 signed (Apple) |
| username | TEXT | Username |
| description | TEXT | Optional user description |
| directory | TEXT | User's home directory |
| shell | TEXT | User's configured default shell |
| uuid | TEXT | User's UUID (Apple) or SID (Windows) |
| type | TEXT | Whether the account is roaming (domain), local, or a system profile |
| is_hidden | INTEGER | IsHidden attribute set in OpenDirectory |
| pid_with_namespace | INTEGER | Pids that contain a namespace |
| include_remote | INTEGER | 1 to include remote (LDAP/AD) accounts (default 0). Warning: without any uid/username filtering it may list whole LDAP directories |

<!-- DCOIR_SOURCE_END {"id":"knowledge.reference.osquery_users","sha256":"e90de964dc00df6fdf1dbfc29c3d02517204b4e56771dd2c72dab58f23aac68d"} -->

<!-- DCOIR_SOURCE_BEGIN {"bytes":27238,"git_blob_sha":"377d96d18442988b90892a9f41425dc71f12b271","id":"knowledge.reference.osquery_virtualization","path":"knowledge/Knowledge - Reference - OSQuery Virtualization, Cloud, and Container Tables.md","sha256":"41e811032dd90b6388964208207f322a3359ee4c6c24c65c0a83ffb5ad111f2d"} -->
# Knowledge - Reference - OSQuery Virtualization, Cloud, and Container Tables

_Exact OSQuery container, virtualization, cloud-metadata, and OSQuery self-state reference tables._

**Summary:** This page preserves the exact OSQuery source markdown for the tables in this shard. Use it as the governed exact-name reference for table and field lookup.

---

### azure_instance_metadata

**Platforms:** MacOS Linux Windows

Azure instance metadata.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| location | TEXT | Azure Region the VM is running in |
| name | TEXT | Name of the VM |
| offer | TEXT | Offer information for the VM image (Azure image gallery VMs only) |
| publisher | TEXT | Publisher of the VM image |
| sku | TEXT | SKU for the VM image |
| version | TEXT | Version of the VM image |
| os_type | TEXT | Linux or Windows |
| platform_update_domain | TEXT | Update domain the VM is running in |
| platform_fault_domain | TEXT | Fault domain the VM is running in |
| vm_id | TEXT | Unique identifier for the VM |
| vm_size | TEXT | VM size |
| subscription_id | TEXT | Azure subscription for the VM |
| resource_group_name | TEXT | Resource group for the VM |
| placement_group_id | TEXT | Placement group for the VM scale set |
| vm_scale_set_name | TEXT | VM scale set name |
| zone | TEXT | Availability zone of the VM |

### azure_instance_tags

**Platforms:** MacOS Linux Windows

Azure instance tags.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| vm_id | TEXT | Unique identifier for the VM |
| key | TEXT | The tag key |
| value | TEXT | The tag value |

### docker_container_envs

**Platforms:** MacOS Linux

Docker container environment variables.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| id | TEXT | Container ID |
| key | TEXT | Environment variable name |
| value | TEXT | Environment variable value |

### docker_container_fs_changes

**Platforms:** MacOS Linux

Changes to files or directories on container's filesystem.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| id | TEXT | Container ID Required in WHERE clause |
| path | TEXT | FIle or directory path relative to rootfs |
| change_type | TEXT | Type of change: C:Modified, A:Added, D:Deleted |

### docker_container_labels

**Platforms:** MacOS Linux

Docker container labels.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| id | TEXT | Container ID |
| key | TEXT | Label key |
| value | TEXT | Optional label value |

### docker_container_mounts

**Platforms:** MacOS Linux

Docker container mounts.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| id | TEXT | Container ID |
| type | TEXT | Type of mount (bind, volume) |
| name | TEXT | Optional mount name |
| source | TEXT | Source path on host |
| destination | TEXT | Destination path inside container |
| driver | TEXT | Driver providing the mount |
| mode | TEXT | Mount options (rw, ro) |
| rw | INTEGER | 1 if read/write. 0 otherwise |
| propagation | TEXT | Mount propagation |

### docker_container_networks

**Platforms:** MacOS Linux

Docker container networks.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| id | TEXT | Container ID |
| name | TEXT | Network name |
| network_id | TEXT | Network ID |
| endpoint_id | TEXT | Endpoint ID |
| gateway | TEXT | Gateway |
| ip_address | TEXT | IP address |
| ip_prefix_len | INTEGER | IP subnet prefix length |
| ipv6_gateway | TEXT | IPv6 gateway |
| ipv6_address | TEXT | IPv6 address |
| ipv6_prefix_len | INTEGER | IPv6 subnet prefix length |
| mac_address | TEXT | MAC address |

### docker_container_ports

**Platforms:** MacOS Linux

Docker container ports.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| id | TEXT | Container ID |
| type | TEXT | Protocol (tcp, udp) |
| port | INTEGER | Port inside the container |
| host_ip | TEXT | Host IP address on which public port is listening |
| host_port | INTEGER | Host port |

### docker_container_processes

**Platforms:** MacOS Linux

Docker container processes.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| id | TEXT | Container ID Required in WHERE clause |
| pid | BIGINT | Process ID |
| name | TEXT | The process path or shorthand argv[0] |
| cmdline | TEXT | Complete argv |
| state | TEXT | Process state |
| uid | BIGINT | User ID |
| gid | BIGINT | Group ID |
| euid | BIGINT | Effective user ID |
| egid | BIGINT | Effective group ID |
| suid | BIGINT | Saved user ID |
| sgid | BIGINT | Saved group ID |
| wired_size | BIGINT | Bytes of unpageable memory used by process |
| resident_size | BIGINT | Bytes of private memory used by process |
| total_size | BIGINT | Total virtual memory size |
| start_time | BIGINT | Process start in seconds since boot (non-sleeping) |
| parent | BIGINT | Process parent's PID |
| pgroup | BIGINT | Process group |
| threads | INTEGER | Number of threads used by process |
| nice | INTEGER | Process nice level (-20 to 20, default 0) |
| user | TEXT | User name |
| time | TEXT | Cumulative CPU time. [DD-]HH:MM:SS format |
| cpu | DOUBLE | CPU utilization as percentage |
| mem | DOUBLE | Memory utilization as percentage |

### docker_container_stats

**Platforms:** MacOS Linux

Docker container statistics. Queries on this table take at least one second.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| id | TEXT | Container ID Required in WHERE clause |
| name | TEXT | Container name |
| pids | INTEGER | Number of processes |
| read | BIGINT | UNIX time when stats were read |
| preread | BIGINT | UNIX time when stats were last read |
| interval | BIGINT | Difference between read and preread in nano-seconds |
| disk_read | BIGINT | Total disk read bytes |
| disk_write | BIGINT | Total disk write bytes |
| num_procs | INTEGER | Number of processors |
| cpu_total_usage | BIGINT | Total CPU usage |
| cpu_kernelmode_usage | BIGINT | CPU kernel mode usage |
| cpu_usermode_usage | BIGINT | CPU user mode usage |
| system_cpu_usage | BIGINT | CPU system usage |
| online_cpus | INTEGER | Online CPUs |
| pre_cpu_total_usage | BIGINT | Last read total CPU usage |
| pre_cpu_kernelmode_usage | BIGINT | Last read CPU kernel mode usage |
| pre_cpu_usermode_usage | BIGINT | Last read CPU user mode usage |
| pre_system_cpu_usage | BIGINT | Last read CPU system usage |
| pre_online_cpus | INTEGER | Last read online CPUs |
| memory_usage | BIGINT | Memory usage |
| memory_cached | BIGINT | Memory cached |
| memory_inactive_file | BIGINT | Memory inactive file |
| memory_total_inactive_file | BIGINT | Memory total inactive file |
| memory_max_usage | BIGINT | Memory maximum usage |
| memory_limit | BIGINT | Memory limit |
| network_rx_bytes | BIGINT | Total network bytes read |
| network_tx_bytes | BIGINT | Total network bytes transmitted |

### docker_containers

**Platforms:** MacOS Linux

Docker containers information.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| id | TEXT | Container ID |
| name | TEXT | Container name |
| image | TEXT | Docker image (name) used to launch this container |
| image_id | TEXT | Docker image ID |
| command | TEXT | Command with arguments |
| created | BIGINT | Time of creation as UNIX time |
| state | TEXT | Container state (created, restarting, running, removing, paused, exited, dead) |
| status | TEXT | Container status information |
| pid | BIGINT | Identifier of the initial process |
| path | TEXT | Container path |
| config_entrypoint | TEXT | Container entrypoint(s) |
| started_at | TEXT | Container start time as string |
| finished_at | TEXT | Container finish time as string |
| privileged | INTEGER | Is the container privileged |
| security_options | TEXT | List of container security options |
| env_variables | TEXT | Container environmental variables |
| readonly_rootfs | INTEGER | Is the root filesystem mounted as read only |
| cgroup_namespace | TEXT | cgroup namespace |
| ipc_namespace | TEXT | IPC namespace |
| mnt_namespace | TEXT | Mount namespace |
| net_namespace | TEXT | Network namespace |
| pid_namespace | TEXT | PID namespace |
| user_namespace | TEXT | User namespace |
| uts_namespace | TEXT | UTS namespace |

### docker_image_history

**Platforms:** MacOS Linux

Docker image history information.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| id | TEXT | Image ID |
| created | BIGINT | Time of creation as UNIX time |
| size | BIGINT | Size of instruction in bytes |
| created_by | TEXT | Created by instruction |
| tags | TEXT | Comma-separated list of tags |
| comment | TEXT | Instruction comment |

### docker_image_labels

**Platforms:** MacOS Linux

Docker image labels.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| id | TEXT | Image ID |
| key | TEXT | Label key |
| value | TEXT | Optional label value |

### docker_image_layers

**Platforms:** MacOS Linux

Docker image layers information.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| id | TEXT | Image ID |
| layer_id | TEXT | Layer ID |
| layer_order | INTEGER | Layer Order (1 = base layer) |

### docker_images

**Platforms:** MacOS Linux

Docker images information.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| id | TEXT | Image ID |
| created | BIGINT | Time of creation as UNIX time |
| size_bytes | BIGINT | Size of image in bytes |
| tags | TEXT | Comma-separated list of repository tags |

### docker_info

**Platforms:** MacOS Linux

Docker system information.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| id | TEXT | Docker system ID |
| containers | INTEGER | Total number of containers |
| containers_running | INTEGER | Number of containers currently running |
| containers_paused | INTEGER | Number of containers in paused state |
| containers_stopped | INTEGER | Number of containers in stopped state |
| images | INTEGER | Number of images |
| storage_driver | TEXT | Storage driver |
| memory_limit | INTEGER | 1 if memory limit support is enabled. 0 otherwise |
| swap_limit | INTEGER | 1 if swap limit support is enabled. 0 otherwise |
| kernel_memory | INTEGER | 1 if kernel memory limit support is enabled. 0 otherwise |
| cpu_cfs_period | INTEGER | 1 if CPU Completely Fair Scheduler (CFS) period support is enabled. 0 otherwise |
| cpu_cfs_quota | INTEGER | 1 if CPU Completely Fair Scheduler (CFS) quota support is enabled. 0 otherwise |
| cpu_shares | INTEGER | 1 if CPU share weighting support is enabled. 0 otherwise |
| cpu_set | INTEGER | 1 if CPU set selection support is enabled. 0 otherwise |
| ipv4_forwarding | INTEGER | 1 if IPv4 forwarding is enabled. 0 otherwise |
| bridge_nf_iptables | INTEGER | 1 if bridge netfilter iptables is enabled. 0 otherwise |
| bridge_nf_ip6tables | INTEGER | 1 if bridge netfilter ip6tables is enabled. 0 otherwise |
| oom_kill_disable | INTEGER | 1 if Out-of-memory kill is disabled. 0 otherwise |
| logging_driver | TEXT | Logging driver |
| cgroup_driver | TEXT | Control groups driver |
| kernel_version | TEXT | Kernel version |
| os | TEXT | Operating system |
| os_type | TEXT | Operating system type |
| architecture | TEXT | Hardware architecture |
| cpus | INTEGER | Number of CPUs |
| memory | BIGINT | Total memory |
| http_proxy | TEXT | HTTP proxy |
| https_proxy | TEXT | HTTPS proxy |
| no_proxy | TEXT | Comma-separated list of domain extensions proxy should not be used for |
| name | TEXT | Name of the docker host |
| server_version | TEXT | Server version |
| root_dir | TEXT | Docker root directory |

### docker_network_labels

**Platforms:** MacOS Linux

Docker network labels.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| id | TEXT | Network ID |
| key | TEXT | Label key |
| value | TEXT | Optional label value |

### docker_networks

**Platforms:** MacOS Linux

Docker networks information.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| id | TEXT | Network ID |
| name | TEXT | Network name |
| driver | TEXT | Network driver |
| created | BIGINT | Time of creation as UNIX time |
| enable_ipv6 | INTEGER | 1 if IPv6 is enabled on this network. 0 otherwise |
| subnet | TEXT | Network subnet |
| gateway | TEXT | Network gateway |

### docker_version

**Platforms:** MacOS Linux

Docker version information.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| version | TEXT | Docker version |
| api_version | TEXT | API version |
| min_api_version | TEXT | Minimum API version supported |
| git_commit | TEXT | Docker build git commit |
| go_version | TEXT | Go version |
| os | TEXT | Operating system |
| arch | TEXT | Hardware architecture |
| kernel_version | TEXT | Kernel version |
| build_time | TEXT | Build time |

### docker_volume_labels

**Platforms:** MacOS Linux

Docker volume labels.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Volume name |
| key | TEXT | Label key |
| value | TEXT | Optional label value |

### docker_volumes

**Platforms:** MacOS Linux

Docker volumes information.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Volume name |
| driver | TEXT | Volume driver |
| mount_point | TEXT | Mount point |
| type | TEXT | Volume type |

### ec2_instance_metadata

**Platforms:** MacOS Linux Windows

EC2 instance metadata.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| instance_id | TEXT | EC2 instance ID |
| instance_type | TEXT | EC2 instance type |
| architecture | TEXT | Hardware architecture of this EC2 instance |
| region | TEXT | AWS region in which this instance launched |
| availability_zone | TEXT | Availability zone in which this instance launched |
| local_hostname | TEXT | Private IPv4 DNS hostname of the first interface of this instance |
| local_ipv4 | TEXT | Private IPv4 address of the first interface of this instance |
| mac | TEXT | MAC address for the first network interface of this EC2 instance |
| security_groups | TEXT | Comma separated list of security group names |
| iam_arn | TEXT | If there is an IAM role associated with the instance, contains instance profile ARN |
| ami_id | TEXT | AMI ID used to launch this EC2 instance |
| reservation_id | TEXT | ID of the reservation |
| account_id | TEXT | AWS account ID which owns this EC2 instance |
| ssh_public_key | TEXT | SSH public key. Only available if supplied at instance launch time |

### ec2_instance_tags

**Platforms:** MacOS Linux Windows

EC2 instance tag key value pairs.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| instance_id | TEXT | EC2 instance ID |
| key | TEXT | Tag key |
| value | TEXT | Tag value |

### lxd_certificates

**Platforms:** Linux

LXD certificates information.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Name of the certificate |
| type | TEXT | Type of the certificate |
| fingerprint | TEXT | SHA256 hash of the certificate |
| certificate | TEXT | Certificate content |

### lxd_cluster

**Platforms:** Linux

LXD cluster information.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| server_name | TEXT | Name of the LXD server node |
| enabled | INTEGER | Whether clustering enabled (1) or not (0) on this node |
| member_config_entity | TEXT | Type of configuration parameter for this node |
| member_config_name | TEXT | Name of configuration parameter |
| member_config_key | TEXT | Config key |
| member_config_value | TEXT | Config value |
| member_config_description | TEXT | Config description |

### lxd_cluster_members

**Platforms:** Linux

LXD cluster members information.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| server_name | TEXT | Name of the LXD server node |
| url | TEXT | URL of the node |
| database | INTEGER | Whether the server is a database node (1) or not (0) |
| status | TEXT | Status of the node (Online/Offline) |
| message | TEXT | Message from the node (Online/Offline) |

### lxd_images

**Platforms:** Linux

LXD images information.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| id | TEXT | Image ID |
| architecture | TEXT | Target architecture for the image |
| os | TEXT | OS on which image is based |
| release | TEXT | OS release version on which the image is based |
| description | TEXT | Image description |
| aliases | TEXT | Comma-separated list of image aliases |
| filename | TEXT | Filename of the image file |
| size | BIGINT | Size of image in bytes |
| auto_update | INTEGER | Whether the image auto-updates (1) or not (0) |
| cached | INTEGER | Whether image is cached (1) or not (0) |
| public | INTEGER | Whether image is public (1) or not (0) |
| created_at | TEXT | ISO time of image creation |
| expires_at | TEXT | ISO time of image expiration |
| uploaded_at | TEXT | ISO time of image upload |
| last_used_at | TEXT | ISO time for the most recent use of this image in terms of container spawn |
| update_source_server | TEXT | Server for image update |
| update_source_protocol | TEXT | Protocol used for image information update and image import from source server |
| update_source_certificate | TEXT | Certificate for update source server |
| update_source_alias | TEXT | Alias of image at update source server |

### lxd_instance_config

**Platforms:** Linux

LXD instance configuration information.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Instance name Required in WHERE clause |
| key | TEXT | Configuration parameter name |
| value | TEXT | Configuration parameter value |

### lxd_instance_devices

**Platforms:** Linux

LXD instance devices information.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Instance name Required in WHERE clause |
| device | TEXT | Name of the device |
| device_type | TEXT | Device type |
| key | TEXT | Device info param name |
| value | TEXT | Device info param value |

### lxd_instances

**Platforms:** Linux

LXD instances information.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Instance name |
| status | TEXT | Instance state (running, stopped, etc.) |
| stateful | INTEGER | Whether the instance is stateful(1) or not(0) |
| ephemeral | INTEGER | Whether the instance is ephemeral(1) or not(0) |
| created_at | TEXT | ISO time of creation |
| base_image | TEXT | ID of image used to launch this instance |
| architecture | TEXT | Instance architecture |
| os | TEXT | The OS of this instance |
| description | TEXT | Instance description |
| pid | INTEGER | Instance's process ID |
| processes | INTEGER | Number of processes running inside this instance |

### lxd_networks

**Platforms:** Linux

LXD network information.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Name of the network |
| type | TEXT | Type of network |
| managed | INTEGER | 1 if network created by LXD, 0 otherwise |
| ipv4_address | TEXT | IPv4 address |
| ipv6_address | TEXT | IPv6 address |
| used_by | TEXT | URLs for containers using this network |
| bytes_received | BIGINT | Number of bytes received on this network |
| bytes_sent | BIGINT | Number of bytes sent on this network |
| packets_received | BIGINT | Number of packets received on this network |
| packets_sent | BIGINT | Number of packets sent on this network |
| hwaddr | TEXT | Hardware address for this network |
| state | TEXT | Network status |
| mtu | INTEGER | MTU size |

### lxd_storage_pools

**Platforms:** Linux

LXD storage pool information.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Name of the storage pool |
| driver | TEXT | Storage driver |
| source | TEXT | Storage pool source |
| size | TEXT | Size of the storage pool |
| space_used | BIGINT | Storage space used in bytes |
| space_total | BIGINT | Total available storage space in bytes for this storage pool |
| inodes_used | BIGINT | Number of inodes used |
| inodes_total | BIGINT | Total number of inodes available in this storage pool |

### osquery_events

**Platforms:** MacOS Linux Windows

Information about the event publishers and subscribers.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Event publisher or subscriber name |
| publisher | TEXT | Name of the associated publisher |
| type | TEXT | Either publisher or subscriber |
| subscriptions | INTEGER | Number of subscriptions the publisher received or subscriber used |
| events | INTEGER | Number of events emitted or received since osquery started |
| refreshes | INTEGER | Publisher only: number of runloop restarts |
| active | INTEGER | 1 if the publisher or subscriber is active else 0 |

### osquery_extensions

**Platforms:** MacOS Linux Windows

List of active osquery extensions.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| uuid | BIGINT | The transient ID assigned for communication |
| name | TEXT | Extension's name |
| version | TEXT | Extension's version |
| sdk_version | TEXT | osquery SDK version used to build the extension |
| path | TEXT | Path of the extension's Thrift connection or library path |
| type | TEXT | SDK extension type: core, extension, or module |

### osquery_flags

**Platforms:** MacOS Linux Windows

Configurable flags that modify osquery's behavior.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | Flag name |
| type | TEXT | Flag type |
| description | TEXT | Flag description |
| default_value | TEXT | Flag default value |
| value | TEXT | Flag value |
| shell_only | INTEGER | Is the flag shell only? |

### osquery_info

**Platforms:** MacOS Linux Windows

Top level information about the running version of osquery.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| pid | INTEGER | Process (or thread/handle) ID |
| uuid | TEXT | Unique ID provided by the system |
| instance_id | TEXT | Unique, long-lived ID per instance of osquery |
| version | TEXT | osquery toolkit version |
| config_hash | TEXT | Hash of the working configuration state |
| config_valid | INTEGER | 1 if the config was loaded and considered valid, else 0 |
| extensions | TEXT | osquery extensions status |
| build_platform | TEXT | osquery toolkit build platform |
| build_distro | TEXT | osquery toolkit platform distribution name (os version) |
| start_time | INTEGER | UNIX time in seconds when the process started |
| watcher | INTEGER | Process (or thread/handle) ID of optional watcher process |
| platform_mask | INTEGER | The osquery platform bitmask |

### osquery_packs

**Platforms:** MacOS Linux Windows

Information about the current query packs that are loaded in osquery.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | The given name for this query pack |
| platform | TEXT | Platforms this query is supported on |
| version | TEXT | Minimum osquery version that this query will run on |
| shard | INTEGER | Shard restriction limit, 1-100, 0 meaning no restriction |
| discovery_cache_hits | INTEGER | The number of times that the discovery query used cached values since the last time the config was reloaded |
| discovery_executions | INTEGER | The number of times that the discovery queries have been executed since the last time the config was reloaded |
| active | INTEGER | Whether this pack is active (the version, platform and discovery queries match) yes=1, no=0. |

### osquery_registry

**Platforms:** MacOS Linux Windows

List the osquery registry plugins.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| registry | TEXT | Name of the osquery registry |
| name | TEXT | Name of the plugin item |
| owner_uuid | INTEGER | Extension route UUID (0 for core) |
| internal | INTEGER | 1 If the plugin is internal else 0 |
| active | INTEGER | 1 If this plugin is active else 0 |

### osquery_schedule

**Platforms:** MacOS Linux Windows

Information about the current queries that are scheduled in osquery.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| name | TEXT | The given name for this query |
| query | TEXT | The exact query to run |
| interval | INTEGER | The interval in seconds to run this query, not an exact interval |
| executions | BIGINT | Number of times the query was executed |
| last_executed | BIGINT | UNIX time stamp in seconds of the last completed execution |
| denylisted | INTEGER | 1 if the query is denylisted else 0 |
| output_size | BIGINT | Cumulative total number of bytes generated by the resultant rows of the query |
| wall_time | BIGINT | Total wall time in seconds spent executing (deprecated), hidden=True |
| wall_time_ms | BIGINT | Total wall time in milliseconds spent executing |
| last_wall_time_ms | BIGINT | Wall time in milliseconds of the latest execution |
| user_time | BIGINT | Total user time in milliseconds spent executing |
| last_user_time | BIGINT | User time in milliseconds of the latest execution |
| system_time | BIGINT | Total system time in milliseconds spent executing |
| last_system_time | BIGINT | System time in milliseconds of the latest execution |
| average_memory | BIGINT | Average of the bytes of resident memory left allocated after collecting results |
| last_memory | BIGINT | Resident memory in bytes left allocated after collecting results of the latest execution |

### prometheus_metrics

**Platforms:** MacOS Linux

Retrieve metrics from a Prometheus server.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| target_name | TEXT | Address of prometheus target |
| metric_name | TEXT | Name of collected Prometheus metric |
| metric_value | DOUBLE | Value of collected Prometheus metric |
| timestamp_ms | BIGINT | Unix timestamp of collected data in MS |

### ycloud_instance_metadata

**Platforms:** MacOS Linux Windows

Yandex.Cloud instance metadata.

Improve this Description on Github

| Column | Type | Description |
|---|---|---|
| instance_id | TEXT | Unique identifier for the VM |
| folder_id | TEXT | Folder identifier for the VM |
| cloud_id | TEXT | Cloud identifier for the VM |
| name | TEXT | Name of the VM |
| description | TEXT | Description of the VM |
| hostname | TEXT | Hostname of the VM |
| zone | TEXT | Availability zone of the VM |
| ssh_public_key | TEXT | SSH public key. Only available if supplied at instance launch time |
| serial_port_enabled | TEXT | Indicates if serial port is enabled for the VM |
| metadata_endpoint | TEXT | Endpoint used to fetch VM metadata |

<!-- DCOIR_SOURCE_END {"id":"knowledge.reference.osquery_virtualization","sha256":"41e811032dd90b6388964208207f322a3359ee4c6c24c65c0a83ffb5ad111f2d"} -->

