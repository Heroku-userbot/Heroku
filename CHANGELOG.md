# Heroku Changelog
## 🪐 Heroku 2.2.0

 - add rich messages support (rich = True) with the {img} placeholder
 - add duplicate command dispatcher: choose which command to run when several modules share a name
 - add multiple prefixes support: `.setprefix` now accepts several prefixes (the first is the main one, the rest are aliases), including personal prefixes of owners and sgroup users
 - add -p argument to owneradd to set a personal prefix for the new owner instead of a separate .setprefix @owner
 - add check if the owner is already added in owneradd
 - add guest bot update
 - add reply_to parameter to Form class and inline message replies
 - add `inline_ready` module hook: called after `client_ready`, when the inline bot is ready (and again, if the bot is recreated)
 - add `loader.InlineDownError`, raised on access to `self.inline.bot` when the inline bot isn't running
 - add the alias `kill` for the `terminate` command
 - rework sudo password input in terminal
 - fix grep usage in terminal and with rich messages, including premium emojis
 - fix premium emojis in the document_id syntax (emoji tag with document_id) not displaying in rich messages
 - fix `e` aliases

 - fix error on `.info` when Telegram rejects an external banner(EXTERNAL_MEDIA_NOT_SUPPORTED)
 - fix proper removal of bot update handlers and references
 - fix LoaderRestrictor check and inline bot initialization, including the unlock prompt on a fresh install
 - fix error logging in inline query and event polling
 - fix several unauthorized sessions asking for the phone number at the same time on start
 - fix backup, updater, quickstart and LoaderRestrictor being unloaded on the first start if the inline bot is unavailable
 - fix startup of the whole client failing if the inline manager initialization raises
 - fix inline bot recreation when the bot is deactivated (frozen): warn and create a new one
 - fix process hanging on unload, add task tracking for asyncio tasks
 - improve WebpageMediaEmpty error
 - improve look of .dlm with multiple modules
 - remove presets module
 - update herokutl to 2.2.0 and clean up requirements
 - improve install.sh and add a workflow for testing it

## 🪐 Heroku 2.1.0

 - fix security check in help
 - fix blockquote in config and info
 - add pip packages backup to backupall
 - fix placeholders in help
 - fix placeholders caption in UwU language
 - fix loader.tag's
 - add dlmall command
 - add banner to .dlm
 - add banner to help
 - fix double prefixes
 - fix RCE in web (add password and user to initializating client)
 - fix bot creation
 - fix chat creation
 - add category in config
 - fix addacc self reply logic
 - add -w and --wipe argument for python3 -m heroku for wipe session, databases, loaded modules
 - add duplicate alias warning with target command name
 - add -f and --force argument to owneradd
 - add -n and --nonick argument to owneradd
 - add ubstop inline confirmation
 - add -f and --force argument to ubstop
 - migrate inline bot from aiogram to HerokuTL
 - add support for receiving Bot API update types in the inline bot
 - add inline terminal input continuation
 - add terminate support for inline terminal sessions
 - add configurable terminal protection boolean
 - fix query_gallery calls when the bot is not mounted
 - remove the web stack, web resources and related Docker/runtime pieces
 - add Rust and Go eval commands
 - add multi addalias and multi alias delete support
 - add -c / --clear for delalias
 - add -f flag for logs
 - add --type-proxy startup option
 - add packurl translation fallback cache
 - add missing language packs
 - add fuzzy suggestions for unload typos
 - improve unknown string handling
 - add loader.download_and_install logging
 - replace direct database access with _get_raw
 - catch AuthKeyUnregisteredError on startup
 - remove custom_emojis handling from inline/config paths
 - simplify config option formatting and category parameter display
 - remove HerokuPluginSecurity
 - fix requirements installation on startup
 - add fuzzy search in config
 - add pagination in config
 - add language aliases for Ukrainian and Japanese
 - refactor inline initialization
 - remove GeekTG compatibility layer
 - remove dead code
 - fix chosen inline message edit
 - fix child watcher
 - fix terminal reply getting logic
 - fix print() censor in .e command
 - fix buttons language
 - fix callable type annotation
 - fix argument of type 'bool' is not iterable exception in inline events
 - fix update banner display logic
 - fix BotFather bot name in UwU strings
 - improve bot update type handling (IDE hints)
 - add basic auth for first-time web initialization
 - add global rate limiting and tunnel closure
 - add restriction for password and username length in web auth
 - decentralize forum and topics creation
 - add debug data to bot creation logs
 - fix check_commit_ancestor
 - fix headers reusing
 - update SSH tunnel regex and add Serveo warning message
 - enhance error logging for bot creation and inline settings changes
 - fix wrong asynchronous function calls
 - add broadcast to asset channel
 - add code escape to error output
 - add print output to error
 - fix clearmodule command logic
 - add output skip flag (-so) to e command
 - fix clearmodules
 - add # meta banner preview for modules
 - add .dlmall command to download all modules from repositories
 - fix invert media answer function
 - fix getting args
 - add # meta developer banner preview to help [module]
 - fix IndexError in config pages
 - avoid unexpected error while deleting inline message
 - remove botfather web implementation
 - add account transfer
 - add new ConfigCategory type
 - remove Jamhost
 - remove command for disabling core protection
 - improve token obtainment logic
 - add category configuration options
 - add support for receiving all Bot API update types via loader.need_update
 - add inline terminal command execution
 - add management for downloaded languages
 - fix help command strings
 - update Dockerfile
 - fix database rights and actualize requirements
 - add wipe command and safety flags
 - fix full backup restore dependencies
 - fix: wrap bot update handlers to bypass aiogram signature inspection
 - fix TelegramClient missing _set_module_info attribute
 - add successful module load debug log
 - feat(config): add expandable blockquote for section parameters display
 - fix(loader): include module name in debug log message
 - fix(heroku_config): simplify formatting of option lines
 - update config formatting
 - refactor: streamline category parameter display
 - add scope for restrict ml (no_ml)
 - fix blocked db write to protected owner from loader
 - improve autoupdate bot message logic
 - remove web
 - fix(Docker): fix image build and GitPython zombie processes, clean unused packages and envs
 - migrate inline bot to Telethon
 - add support for receiving all bot API updates 
 - reload bot update handlers on module unload 
 - replace &lt;emoji&gt; tag with &lt;tg-emoji&gt;
 - support direct TL request execution via <b>call</b>
 - add asyncio timeout to update retrieval function
 - fix bugs
 - modernize typing, format with Black and small cleanups
 - refactor inline init and add ping bot function
 - remove lavhost
 - fix premium check
 - update validators for emoji 1.x/2.x compat
 - fix git zombie processes in updater
 - migrate session management to dedicated sessions directory
 - restrict ability to ml LoaderRestrictor module
 - store bot's ID and user information in client instance
 - enhance reaction handling and improve message text update logic

## 🪐 Heroku 2.0.0

- rework utils
- add prefix to start message
- fix create bot
- remove debugger
- improve error message
- add protection in terminal
- add media_quote, invert_media to help, ping and info cmds
- remove "heroku" from bot username
- fix asset channel
- add entity validation for setprefix
- update readme
- add utils.get_platform_named_emoji
- add multiload
- fix error in help lib
- add config to internet error ignore
- update heroku-tl to 2.0.0
- add time execution to eval and terminal
- add type annotations (developer oriented)
- add japanese language
- add french language
- add protection for messages from 777000 and 489000
- add help -c (core modules) and help -l (loaded modules)
- new info
- fix folders
- rework bot creation
- add python version in info
- remove -S flag from sudo
- add link validator to help, info, ping
- add meme lang packs
- add UwU language to meme pack
- add leet(1337) to meme pack
- add tiktokkid to meme pack
- remove support python 3.9
- rework if else to match/case
- add utils.format_file_size
- add utils.is_url
- add utils.get_iso_time
- add utils.safe_getattr
- add utils.get_last_commit_message
- add utils.get_commit_count
- add utils.get_hostname
- add utils.resolve_domain
- add utils.is_port_open
- add utils.get_network_interfaces
- add utils.get_disk_usage
- add utils.get_ip_address
- add utils.get_args_bool
- add utils.get_args_int
- fix pack_url
- add togglecmd cmd for disable or enable any cmd
- add togglemod cmd for disable or enable any module
- add clearmodule cmd
- add placeholder system
- move all log chat to forumTopics
- add execution in .e from reply
- add utils.asset_forum_topic
- add utils.create_topic
- add operator to fcfg
- remove invokecmd
- remove uninstall_herokucmd
- remove debugmodcmd
- add new validator RandomLink
- replace validators in help, herokuinfo, tester to RandomLink
- add and remove some modules in presets
- replace TgCrypto to TgCrypto-pyrofork
- impove keyboard layout
- refactor clean up socket path assignment handling
- improve platform model detection
- add blockquote to dlm and lm cmds
- improve boolean validation
- add requirements installation when launching the userbot
- add mini protection in eval
- fix database path
- fconfig value from reply
- migrate from json to orjson
- backupall send backup in backupchat
- fully remove save to fs
- optimize username handling & fix logic
- protection for session files
- add premium emoji in some cases with inline
- add developer in help
- add folder for config
- remove pyproject.toml
- add more session protection
- add custom presets
- add message about no query answer
- add ulm -f
- fix permission denied in info 
- add hiding the phone in htl
- add more protection for official telegram account (777000)
- add button styles support for the inline bot stack (danger, primary, success)
- add premium emoji support in buttons via icon_custom_emoji_id
- add aliases export/import
- add folders
- restrict inline queries for not allowed users
- add new styles button in some cases
- add some "icons" in buttons
- remove utils.html_escape from eval
- fix watcherbl
- remove blacklist from ubguard.codrago.life
- fix config mod args when args is wrong
- add some translation providers to translator
- fix: replace all no-break spaces with regular ones in Evaluator
- add premium icon to /start and /profile
- fix critical bug with inline
- fix: update hashable_entity check to handle negative channel ID's
- add bot command adding
- improve error handling and add debug logging for bot command settings 
- remove watchdog func from tester
- remove info in photo switch
- remove show_heroku from info
- improve presets button translations
- fix restore button invoke
- improve logging logic

## 🪐 Heroku 1.7.2

- added autoupdate
- updated heroku-tl to 1.7.2
- fix folder bug
- fix request_join in quickstart
- improve request_join logic
- fixed hikkalls
- added multiunload 
- fixed command for anonimous user 
- removed executor
- added print output in eval
- aliases with arguments (.addalias alias command args)
- prefixes for owners
- fix sudo mode 
- removed aeza from info
- fixed bug in help with quote
- loging improvements
- add invert_media in heroku-tl
- fix zero CPU %
- added config split
- added command addacc for add account like a weburl without web
- fixed sorting function in help
- added initial web stop
- fixed all bugs with tsec, sgroups and owners
- fix loader inline_restart
- added modules selection in presets
- fix all updater cmds for lavhost
- refactor close button
- fix _mod_import_lib
- added stop command
- refactor utils.answer logic
- added back button in many menus
- update support command
- added quote for list commands in help
- fix banner in .presets command

## 🪐 Heroku 1.7.1

- fixed bug with web 
- fixed bug with executor
- fixed bug with presets command
- added structure for windows and MacOS
- added blockquote for all lists
- updated all banners and avatars
- added ubguard.codrago.life
- added /profile command in inline bot
- added restart button on "requirements installed"
- removed cloudflare from weburl
- update dockerfile
- update heroku-tl to 1.1.3
- fixed error with "method not mounted"
- added bot polling sleep log to ignore filter

## 🪐 Heroku 1.7.0

- added banner to ping
- added config for emoji in config (.cfg herokuconfig)
- fixed close button in .update
- added several variables to info ({os}, {kernel}, {cpu}, {ping})
- added command to rollback updates
- merged updater & update_notifier and translations
- added command to change bot token (ch_bot_token)
- added first official hosting (@jamhost, also @hikkahost)
- fixed bug with reply in info
- fixed bug with non-working .ping and .info on arch linux
- updated .installation command
- Telethon has been completely updated, moving to heroku-tl
- update heroku-tl to 1.1.0
- added prefix to ping
- removed official support serv00, tothost, goorm, railway, termux
- rename folder "hikka" to "heroku"
- fix close btn
- fix native imports
- added converting Hikka backups to Heroku
- updated inline bot stack
- fix some bugs with buttons in inline

## 🪐 Heroku 1.6.8

- Finally renamed to Heroku and new Emoji
- many changes and improvements
- many bugs fixed, work sped up
- replacing UpgradedEval with Executor
- added non-standard prefixes
- All banners, chats and avatars have been replaced.
- fixed bug with disabling debugger
- removed the button with info (hotfix for a bug where it was reinstalled)
- added config for emoji in aliases (.cfg settings)
- added config for the first emoji to help (.cfg help)
- minor bug fixes
- new design in some built-in elements
- fixed links in /presets, now modules are installed without problems
- added several variables to info and ping ({hostname}, {user})
- added .presets command
- fixed bug with "bot.inline.send.message is never awaited"
- added DJHost in info
- added config for profile picture in info
- added config for show "Heroku" in info
- removed UnitHeta

## 🌑 Heroku 1.6.7

- new design
- added changelog command
- added presets command
- better design in help
- fix strings
- removed command pbe
  
## 🌑 Heroku 1.6.6

- add ToThost, oracle, AWS, aeza and serv00 detection
- fixed some bugs
- update telethon version to 1.37.0
- removed all languages excluding: Russian, English, Ukrainian
  
## 🌑 Heroku 1.6.6 beta

- formatting ruff
- add webapp support in inline buttons
- add random version name
- fix UnicodeDecodeError in windows
- add a new language Ukrainian

## 🌑 Heroku 1.6.5

- fixed several links
- improved desing
- Update to Heroku-TL 2.0.8
- other improvements and fixes...
 
## 🌑 Heroku 1.6.4

- Completely remove Dragon support as redundant
- Fix request_join error
- Decrease module info length in heta
- Add privacy switch to `UnitHeta`
- Add HikkaHost as a platform
- Update to Hikka-TL 2.0.7
- Allow double-restart
- Personal messages scam modules protection
- https://github.com/ZetGoHack/Heroku/issues/115
- https://github.com/ZetGoHack/Heroku/issues/114
- https://github.com/ZetGoHack/Heroku/issues/119
- https://github.com/ZetGoHack/Heroku/issues/120
- Other changes

## 🌑 Heroku 1.6.3

- Add argument `item_type` to `db.pointer` to provide interface for NamedTuple objects
- Add correct exception propagation to inline units
- Add `-fs` arg to `.lm` command
- Add IDM `flush_loader_cache`
- Add ability to cancel QR login using keyboard interrupt
- Add custom security groups
- Add automatic NoNick for tsec methods
- Add external debugging feature (off by default)
- Fix form invoke error message
- Fix `Backuper`
- Fix backward compatiblity with security groups `SUDO` (0x2) and `SUPPORT` (0x4)
- Fix quickstart language buttons translations
- Fix language buttons disabling on restart
- Migrate inline heta search to userbot instead of centralized service
- Cosmetical changes

## 🌑 Heroku 1.6.2

- Fix security issue with edited channel messages
- Add interface to interact with raw pointer data (`.data` attribute)
- Translation fixes
- Randomize `device_model` to bypass fraud detection
- Pass proper device information to Telegram
- Update `hikka-tl` in accordance to upstream telethon v1
- Update `hikka-pyro` in accordance to upstream pyrogram
- Rename packages so that they don't conflict with originals
- Partially migrate to `pathlib`
- Code cleanup
- Add ability to log in using QR code and --no-web
- Disable web interface for Termux and fallback to CLI login instead
- Add fancy ANSI banners
- Add guidelines to `--no-web` login
- Fix session not being saved after logging in using QR without 2fa
- Minify static assets in web
- Replace snowfall with sakura flowers
- Update Termux installation design
- Whitelist requests in APILimiter to ignore internals
- Start web when using `.weburl` and `--no-web` is used
- Add inline commands targeted security rules control
- Completely remove security groups `sudo` and `support`
- Fix proxy-pass
- New core modules: `UnitHeta`, `Translator`
- New watcher tags: `no_pm`, `no_channels`, `no_groups`, `no_inline`, `no_stickers`, `no_docs`, `no_audios`, `no_videos`, `no_photos`, `no_forwards`, `no_reply`, `no_mention`, `mention`, `only_reply`, `only_forwards`
- Remove default presets since they are the security risk
- Update and extend Tatar translation pack
- Restrict setting `s` as command prefix, since it will break command `setprefix`
- Transfer all previously non-essential modules to core ones
- Add alternative translation mechanism using YAML

## 🌑 Heroku 1.6.1

- Remove miyahost from official hosts
- Fix memory leak when using 1.6.0 inside Docker
- Fix userbot dying after restart on Docker
- Root out stats mechanism
- Add French translation pack

## 🌑 Heroku 1.6.0

- Bring support for Dragon Userbot modules
- Make `db` attribute of `Modules` public
- Mess up with some translations
- Fix `.helphide` command
- Fix visual bug with phone input field in web
- Fix proxy-passing in web
- Fix `EntityLike` validator
- Fix stringifying error in logging
- Fix command escaping when using layout translated prefix
- Patch `.info`, `utils.answer` etc to support forums (topics)
- Drop Okteto support
- Show Heroku platform and version in Telegram sessions list
- New type `DragonModule`
- New argument of `get_prefix` - `userbot`. Pass in `"dragon"` to get its prefix
- New attribute of `Modules` - `dragon_modules`
- New attribute of `CustomTelegramClient` - `pyro_proxy`. Use pyrogram methods natively
- New appearence of `help` command
- New module loading animation
- New README.md with installation steps and new web recording
- New `utils.atexit` method
- New `utils.get_topic` method
- New `utils.answer_file` method
- New `utils.get_cpu_usage` method
- New `utils.get_ram_usage` method
- New restart process, which correctly kills all child processes and threads
- New interactive web werkzeug debugger (view pin using `.debugpin` command)
- New QR login flow
- New license banners
- New error-specific messages for RPCErrors, FloodWaitErrors, NetworkErrors
- Send `start` hook to `InfiniteLoop` instances with `autostart` flag only after `client_ready`
- Replace `__getattr__` in `Module` object with properties for commands and handlers
- Move from monkey-patching concept of filling modules' attributes to native one
- Minor and major bugfixes, adapt to topics
- Kazakh translation pack
- Italian translation pack
- Partial Tatar translation pack
- Logging tweaks
- Add `caller` field to inline units
- Add ability to get module help by command alias
- Add ability to decorate aliases with `@loader.command` decorator
- Add credits to developers and translators
- Add support for multiple usernames
- Add topic guesser in `send_message`, `send_file` in order for old modules to work properly
- Add local storage fallback in case remote end is not available
- Add `self.invoke` method for modules
- Fresh Christmas web design
- EULA warning for lavHost and MiyaHost
- Support for Python 3.10

## 🌑 Heroku 1.5.3

- Add Uzbek, Turkish, German and Spanish translation packs
- Fix module and command docs not being translated on-the-flight
- Fix `RegExp` validator

## 🌑 Heroku 1.5.2

- Change the behavior of `@loader.raw_handler` decorator to accept starred arguments instead of list-like value

## 🌑 Heroku 1.5.1

- Fix `--no-web` arg
- Fix `tglog_level` config option of module `Tester`
- Fix duplicated monkey on login page
- Fix shit modules with uppercase commands
- Add physical `Enter` button to login page on mobile devices
- Add `--proxy-pass` arg
- Add `utils.invite_inline_bot` method
- Add `utils.iter_attrs` method
- Add `@loader.raw_handler` decorator
- Add `invite_bot` parameter to `utils.asset_channel`
- Add support for `String` validator's `min_len` and `max_len` parameters

## 🌑 Heroku 1.5.0

- Fix `on_change` param processing in config
- Fix `hikka.types.CoreOverwriteError`
- Fix incorrect commit in info for users with multiple origins
- Fix error with module configs not being updated to values which were set by user
- Fix core unload and core overwrite errors not being raised correctly
- Fix config descriptions in `APIRatelimiter`
- Fix `CoreOverwriteError` handling
- Fix `TelegramID` validator to work with values between 2^32 and 2^64 - 1
- Fix web authorization messages being sent twice
- Fix duplicated animations in web
- Fix installation banner being shown after auth in web
- Fix form placeholder button being shown when not necessary
- Add `@loader.tag(thumb_url="")` decorator
- Add new inline help format
- Add internal method for debug calls (`.invoke`)
- Add Internal Debug Method (IDM) to inspect cache (`inspect_cache`)
- Add IDM `inspect_modules`
- Add IDM `clear_cache`, `clear_entity_cache`, `clear_fulluser_cache`, `clear_fullchannel_cache`, `clear_perms_cache`
- Add IDM `reload_core` to automatically reload core modules from disk
- Add ability to create custom IDMs
- Add fields `flags` and `description` to `RegExp` validator
- Add fields `min_len` and `max_len` to `String` validator
- Add `Emoji` validator
- Add `EntityLike` validator
- Add `hikka.validators.MultiChoice`
- Add `utils.get_args_html` to get arguments of command with HTML
- Add switch to mute @BotFather only once in hikka inline
- Add ability to forbid certain tl methods using `.config APIRatelimiter`
- Add new web interface design
- Add new code input design
- Add new 2fa password input design
- Add ability to set custom emojis in `.info` using command `.setinfo`. In order to use it, remove buttons using config
- Add full trace locals length limit
- Rework full trace locals to hashable converter
- Patch internal help module with bugfixes
- Clean type-hint mess, document utils and other methods, which were undocumented
- Remove redundant non-working code from configurator
- Remove redundant useless params `--hosting`, `--no-nickname`, `--token`, `--web-only`, `--docker-deps-internal`
- Migrate to lazy string interpolation in logging
- Reformat the whole code to match the desired code style
- Rename `APIRatelimiter` -> `APILimiter`
- Enable `joinChannel` and `importChatInvite` calls-by-external-modules blockage for all users by default
- Change inline query placeholder to `user@hikka:~$` + legacy migration
- Completely drop Heroku support due to legacy code, limits and removing of free tier
- Allow user to send code only once to prevent FloodWaits
- Remove junk collector from tl cacher to keep old records so devs can access them w\o making new requests
- Remove FTG License in fully changed files
- Add official GoormIDE support

## 🌑 Heroku 1.4.2

- Fix authorization error

## 🌑 Heroku 1.4.1

- Create new type :obj:`hikka.tl_cache.CustomTelegramClient` to avoid monkeypatching
- Add `ttl` param for :method:`hikka.utils.asset_channel`
- Add support for custom branches (e.g. for beta testers and users, who rolled back)
- Fix automatic modules reactions
- Fix :method:`hikka.inline.utils.Utils._find_caller_sec_map`
- Fix the targeted security rules without time limit
- Require Heroku-TL >= 1.24.9
- Refactor `document_id` of custom emojis
- Refactor validators to be classes, not functions
- Refactor typehints

## 🌑 Heroku 1.4.0

- Publish hikka telethon fork and migrate to it in requirements, thereby fixing the deployment error on Heroku
- Add custom emojis filter to `utils.remove_html`
- Fix `client.get_perms_cached`
- Fix translation flaw in `HerokuSecurity`
- Fix `.uninstall_hikka` being accessible by sudo
- Fix `utils.find_caller` for :method:`hikka.inline.utils.Utils._find_caller_sec_map`
- Fix `.eval`
- Fix: use old lib if its version is higher than new one
- Fix grep for messages bigger than 4096 UTF-8 characters
- Add more animated emojis to modules
- Add targeted security for users and chats (`.tsec`)
- Add support for `tg_level` in `.config Tester`
- Add `-f` param to `.restart` and `.update`
- Add platform-specific Heroku emojis to premium users
- Add codepaces to `utils.get_named_platform`
- Add `Presets` core module
- Add handler for `/start` command in inlinebot with userbot info
- Rename `func` tag to `filter` due to internal python conflict with dynamically generated methods
- Partially rework security unit
- Internal refactoring and typehints
- Remove custom :obj:`BotInlineMessage` hook for :method:`answer`

## 🌑 Heroku 1.3.3

- Fix typo, which broke `client.get_fulluser`

## 🌑 Heroku 1.3.2

- Add `on_change` param to `loader.ConfigValue`
- Rework commands\inline handlers\callback handlers\watchers registration and unload process
- Rework tags processing
- Add junk collector aka reloader to `Modules`

## 🌑 Heroku 1.3.1

- Add caching to `utils.asset_channel`
- Add `channel` param to `utils.asset_channel` to actually create a channel, not supergroup
- Add watcher tags: `startswith`, `endswith`, `contains`, `regex`, `func`, `from_id`, `chat_id`
- Add buttons to `Choice` validator in `.config`
- Add new types: `PointerList`, `PointerDict`
- Add `db.pointer`
- Add `self.pointer` to module and library instances
- Add support for multiaccounting on Heroku
- Add ability to edit only reply markup or only media of message, w/o touching the actual text
- Add support for `@loader.command`-like commands in inline caller finder
- Add `utils.find_caller`
- Add possible cause of error in logs (module and method)
- Add `client.get_perms_cached` to cache native `client.get_permissions`
- Add `client.get_fullchannel` with cache
- Add `client.get_fulluser` with cache
- Add `exp` and `force` params to `client.get_perms_cached` and `client.get_entity`
- Add `exp` cached values check in `client.get_perms_cached` and `client.get_entity`
- Add text validation to info (automatically remove broken tags)
- Add `utils.validate_html` to remove broken tags from text
- Change errors format in web to more human-readable
- Change visible line of traceback in logs to be the last one
- Fix bug with custom_bot option on installation page
- Fix `RecursionError` in entity cacher
- Fix command execution with space between prefix and command
- Fix `utils.answer` for forwarded messages
- Remove `heroku3` from classic requirements, along with heroku installation code snippet
- Remove `termux_requirements.txt`
- Remove legacy `self.get` migration from strings
- Move `hikka._types` to `hikka.types` with legacy support
- Remake all core modules to decorators
- Force custom hikka telethon installation with 144 layer support
- Add animated emojis to core modules strings
- Add trigger to toggle the appearence of custom emojis

## 🌑 Heroku 1.3.0

- Patch stats so they correctly recognize links
- Fix bug when `...` is being replaced with `..` (unnecessary prefix escape)
- Add `@loader.tag`
- Add watcher tags: `no_commands`, `only_commands`, `out`, `in`, `only_messages`, `editable`, `no_media`, `only_media`, `only_photos`, `only_videos`, `only_audios`, `only_docs`, `only_stickers`, `only_inline`, `only_channels`, `only_groups`, `only_pm`. See docs for detailed info
- Add `utils.mime_type` to get mime_type of file in message
- Replace token obtainment mechanism with callback instead of inline
- Do not cut off prefix in `message.message`, `message.text` and `message.raw_text`
- Partially rework events processing and dispatching
- Attempt to fix cached entities mixing up
- Do not update modules in db when secure boot is active
- Refactor members getterr
- Add uptime to `.info`
- Refactor `.help`, add version to single mod help message
- Fix TypeError in `.e` when returning tl class instead of object
- Remove stupid db lock in `.e`
- Allow `.security` and `.inlinesec` only to owner by default
- Add support for `# requires` metatag in libraries
- Add support for `# scope: hikka_min` metatag in libraries
- Send stats of libraries, if enabled in `.settings`
- Replace library existence check from source url to classname
- Add `self.inline` to libraries
- Add `@loader.command`, `@loader.watcher`, `@loader.inline_handler`, `@loader.callback_handler`
- Add support for multiple watchers
- Add support for command translate directly in decorator (`@loader.command(ru_doc="Привет")`)
- Add support for bot messages in `utils.get_chat_id`
- Add human-readable error message when trying to unload core module
- Replace `print` with `logging.info` in main script to make url visible in logs
- Automatically react to module post in developer's channel if possible

## 🌑 Heroku 1.2.12

- Automatically patch reply markup in inline form in the way, that edit stays available anyway
- Do not unload inline form automatically, keep it for 10 minutes instead
- Use `telethon.utils.resolve_inline_message_id` to remove inline unit
- Add `self.request_join`
- Allow developers to declare `client_ready` without arguments

## 🌑 Heroku 1.2.11

- Add support for lib attribute `version` (must be defined BEFORE `init` method)
- Add `self.lookup` to libs
- Add `self.allmodules` to libs
- Add `self._lib_get` to libs
- Add `self._lib_set` to libs
- Add `self.get_prefix` to libs
- Add `self.tg_id` to libs
- Add `client.tg_id` to every TelegramClient
- Add support for hook `on_lib_update` (invoked when library is being updated by new version)
- Add adequate library migration with references replacement
- Add support for markup, generated for messages, sent by bot itself
- Reformat code with `black --preview`
- Automatically send photo as gif if possible in form
- Update quickstart
- New fields in HerokuInfo
- Remove suffix `Heroku` if user specified it somewhere below
- New exception handler
- Fix back button in `.config <lib>`
- New `.e` error format
- Ignore folder creation error
- Fix unload error in module without commands
- Rework inline media processing on edit

## 🌑 Heroku 1.2.10

- Completely drop fast_uploader support
- Add :method:`utils.import_lib`
- Add protection for :obj:`CheckChatInviteRequest` in forbid_joins
- Add ability to search modules by classname in :method:`self.lookup`
- Add anonymous stats of modules loading (YOU CAN DISABLE THEM IN `.settings`)
- Add telethon objects formatting in `.e`
- Add :obj:`loader.SelfSuspend` to disable module commands and watcher loading, e.g. if library is unavailable
- Add migration native modules db storage from `strings["name"]` to classname. ⚠️ Might break some stuff in the beginning in rare cases
- Fix heroku-specific config error

## 🌑 Heroku 1.2.9

- Small patch which allows developer to specify audio metadata in form and `_edit_unit`

## 🌑 Heroku 1.2.8

- Add automatic webpage bot unblock in heroku waker
- Add secure boot feature
- Update native heroku postgre database saving method
- Add easter egg to `.ping`
- Add platform-specific errors while installing requirements
- Change postgresql column `id` datatype from int32 to int64 + legacy migration
- Change proxypass tunnel behavior - now it only opens on setup and via command `.weburl`
- Lavhost-specific web url
- Meaningful errors in web
- ⚠️ Drop `fast_uploader` support. It will be completely removed in next major update
- Deepsource fixes
- Multiple languages with priority

## 🌑 Heroku 1.2.7

- Add automatic proxy pass
- Fix --no-web argument parsing
- Fix localization error in updater
- Print out only INFO statements to stdout
- Add rotating file handler (logfile with max 10MB size)
- Show web endpoint on startup if available
- Fix gallery `inline_message_id` error
- Add support for `custom_buttons` in `inline.list`
- Add support for `custom_buttons` in `inline.gallery`
- Smart fast_uploader (Do not use hard download on files smaller than 1 MB)
- Attempt to parse `unit_id` from passed `InlineCall` object in `inline._delete_unit_message`
- Reformatting
- Change typehints
- Show list-like values in formatted way in config
- Properly escape html in config
- Split config to pages and categories (core \ non-core)
- Properly edit dictionary config (iter)
- Properly remove items from series options through built-in configurator
- Remove warning from web by replacing coroutine generation with `functools.partial`

## 🌑 Heroku 1.2.6

- Fix processing of `# scope: hikka_min`
- Add `forbid_joins.py` (to use it, download module from official repo with the same name)

## 🌑 Heroku 1.2.5

- Add additional exit on restart to avoid port block
- Add unloaded module name on `.unloadmod`
- Add `banner_url` config var to `HerokuInfo`
- Add `loader.validators.Hidden`
- Add `websockets` dependency, so users can load hikarichat on Heroku
- Add `reply_markup` kwarg to `utils.answer`. This will automatically add buttons to plain message or edit buttons of inline unit
- Add suggestion to join developer's channel on module load if available
- Add `client.force_get_entity` to bypass Heroku Cacher
- Add clickable link to loaded module message if specified meta developer is channel
- Add support of `action` attributes for buttons ("action": "close", "action": "unload", "action": "answer")
- Add log splitter between different clients of instance (if possible)
- Fix inline events `IndexError`
- Fix text in inline input
- Fix translation issue in HerokuConfig
- Fix `.dump`
- Fix modules list reset if you perform `.dlmod` when userbot is not yet fully loaded
- Update links in README
- Remove nalinor from official repos until new modules appear

## 🌑 Heroku 1.2.4

- Show current options in module config
- Add new validators: `loader.validators.Union`, `loader.validators.NoneType`
- Add additional Heroku deps
- Fix `load_module` reattempt
- Reorder database read-writes to make postgres the ladder
- Make redis optional for non-heroku users
- Add source to Pipfile
- New Heroku dependencies list in Pipfile
- External Redis database support
- Mask more options in logs and .e output
- Remove psycopg2 from requirements.txt
- New installation banner
- Add automatic blob->raw convertion in loader
- Add banner with Heroku installation status
- Reorder config saving in web
- Fix `Unauthorized` error on Heroku

## 🌑 Heroku 1.2.3

- Add field `action` to inline buttons. You can pass there `close` to close inline form, `unload` to unload it from memory, `answer` & `text` | `show_alert` to answer callback query with message
- Update docstrings in inline to match unified format
- Add surrogate error ignorance in dispatcher
- Fix :obj:`EntityCache` caching username `@None`
- Return :obj:`InlineMessage` in `hikka.inline.gallery.Gallery.gallery`
- Fix typo in docstring

## 🌑 Heroku 1.2.2

- Update gitignore so git doesn't count shit on heroku
- Visual heroku fixes in updater
- Deepsource fixes
- Add `utils.get_entity_url`, `utils.get_message_link`, `utils.remove_html`, `utils.get_kwargs`
- Disable modules debugging on heroku
- Add `.nonickusers`, `.nonickcmds`, `.nonickchats`
- Update blacklist command docs
- Fix grep removing everything in <...>
- Add `loader.validators.RegExp`
- Automatically convert `None` to empty string \ zero integer etc., if validator is specified
- More meaningful errors in `inline_handler`s
- More meaningful errors in `self.inline.form`, `self.inline.gallery`, `self.inline.list` on user-side
- Allow editing\adding media to form via `call.edit`. Currently supported: `photo`, `file`, `video`, `audio`, `gif`

## 🌑 Heroku 1.2.1

- Add termux specific requirements
- Refactor `heroku.py` app searching algorithm
- Refactor postgresql database saving process
- Fix heroku restart message not being edited
- Add heroku waker
- Make `hikka-` app naming optional

## 🌑 Heroku 1.2.0

- Add full-featured Heroku support with additional buildpacks
- Notify which dependencies are being installed in .dlmod
- Additional GeekTG compat layer
- Fix logging chat
- Rework sessions storage and retrieval
- Rework session processing in web

## 🌘 Patch released

- Allow adding and removing multiple items in config
- Add `ast.literal_eval` to config
- Add explicit typecheck for `mod.config`

## 🌑 Heroku 1.1.28

- Fix non-working param `share_link` in loader
- Assure logging bot is a member of logchat
- Do not store partial phone number in session, only ID
- Rework fast uploader so more types can be passed. For more information check code docstrings and typehints
- Rework installer so it properly displays which action is currently happening
- Fix `Series` not accepting one item
- Show upcoming commit in update and warn if update is not required
- Add reset to default button to config
- Merge `hikka_logger.py` with `test.py`
- Localization
- Allow opening options of specific mod via arguments in `.config`
- Add `add` and `remove` buttons to `Series` params
- Do not unload form immediately, if `ttl` param was passed explicitly

## 🌑 Heroku 1.1.27

- Reorder the steps of parsing in `loader.validators.Series`
- Fix aliases (yet another time)
- Fix minor bug in `loader.validators.Series`, which allowed to put empty string in it
- Fix some translation issues and type conversion ones
- Fix incorrect modules loading if multiple links end with specified name
- Fix type conversion bug in `loader.validators.String`
- Fix typehints flaws
- Add additional fields to `inline.form`: `gif`, `file`, `mime\_type`, `video`, `location`, `audio`
- Add reset-to-default action, if config is invalid while loading the userbot to prevent fall
- Add verification emoji to `input` to let user know, that new value was processed
- Add badge showing how much the last restart took
- Add `min_len`, `max_len`, `fixed_len` params to `loader.validators.Series`
- Add option to show downloaded module link in result message of `.dlmod`
- Add explicit database save after applying new config
- Add hint to web
- Add code of conduct
- Add changelog
- Remove redundant code in `database.py` as it literally does nothing

## 🌑 Heroku 1.1.26

- Hopefully finally fix aliases being reset after restart
- Remove redundant internal hook \_client_ready2
- Show user evaluated version of config value instead of pre-comp one
- Add validator for each item to Series, remove separator
- Add new validator: TelegramID

## 🌑 Heroku 1.1.25

- Add separate messages on restart and full_restart. Second one is shown, when all modules are loaded
- Replace .uninstall_hikka with full uninstallation (remove bot, asset chats and folder)
- Suggest update if it is required by module
- New validator: Float
- Buttons in .config of option is a boolean value
- Drop support of argument positive in loader.validators.Integer as it can be easily replaced with minimum=0
- Update semantic generator in validators
- Yet another protection from monkey-patching

## 🌑 Heroku 1.1.24

- Add String and Link validators
- Fix Series validator
- Reformat core modules to use validators

## 🌑 Heroku 1.1.23

- Add config validators (loader.validators, Boolean, Integer, Choice, Series)
- Change info layout
- Add .uninstall_hikka
- Add .clearlogs
- Refactor code
- Fix minor bugs
- Fix aliases being reset after restart (aliases will now be available only when userbot is fully loaded)

## 🌑 Heroku 1.1.22

- Fix bugs related to web, more specifically: Session save timing, adding more than 1 account and proper restart
- Rework Dockerfiles so they work properly
- Add uvloop so the asyncio runs faster
- Add Docker badge to info
- Improve Okteto performance by adjusting settings in okteto-stack.yml
- New ascii_faces in utils
- Typehints update
- Fix Okteto pinger messages removal

## 🌑 Heroku 1.1.21

- Fix translation typos
- Add nonick suggestion when adding user to group
- Add entity caching

## 🌑 Heroku 1.1.20

- Add legacy fs modules migration
- Add ready asyncio Event to help track userbot loading process from outside
- Replace logging in loader with module-dependent one
- Fix some bugs and bug-risk issues
- Send big logs as file, rather than an infinite series of messages
- HTML-escape # meta developer:
- Make self.animate available for core modules and modules, loaded from file

## 🌑 Heroku 1.1.19

- Fix infinite loops
- Add client-specific check of fs modules
- Use classname of module, if it is possible to parse it with ast
- Rework infinite loops stopping and modules instance placement

## 🌑 Heroku 1.1.18

- Add notification about not exact match in help
- Add automatic progress bar generation to self.fast_upload and self.fast_download
- Make Mod ending in modules class name not mandatory

## 🌑 Heroku 1.1.17

- Fix some weird looking code
- Fix some emojies and translation issues
- Add native lavHost support (.restart, .update) via internal API
- Add utils.get_lang_flag()

## 🌑 Heroku 1.1.16

- Fix config docstrings and html escaping
- Fix typehints
- Fix some security staff
- Add additional bot username check
- Add additional foolchecks
- Migrate to walrus operator where necessary
- Remove redundant code block
- Add default inline bot parse mode
- Rename some core stuff which was not supposed to be used by external developers

## 🌑 Heroku 1.1.15

- Add automatic database autofix and rollback if database was broken by module
- Fix translation issues
- Warn user, if he tries to view .help when userbot is not yet fully loaded
- Create alias for \_generate_markup (generate_markup)
- Fix modules which are deleting from helphide
- Automatically save db if it was edited via classic dictionary methods

## 🌑 Heroku 1.1.14

- Fix utils.asset_channel()'s archive param
- Fix defect, which forced installation from additional trusted repo, rather than from primary one if the file names are matched
- Add avatar to utils.asset_channel() which automatically sets chat pic on creation (be careful, bc it leads to floodwaits, if you do it often)
- Add automatic hikka folder processing
- Add avatars to all official repo modules, which require asset chats (and add them to hikka folder)
- Rework database assets chat processing
- Replace some minor stuff like texts and emojies
- Force many core modules to use self.get\self.set rather than digging the db
- Add .fconfig command to forcefully set known config value if it doesn't fit in Telegram query
- Add dataclasses for module config (read the docs for more info), bc old way is blasphemy
- Automatically save config value if it was set to module self.config\[option\] = value
- Add utils.is_serializable(), utils.set_avatar()
- Send very large (over 4096\*10 symbols) output in a file rather than in an inline list

## 🌑 Heroku 1.1.13

- Fix processing commands on behalf of channel
- Fix .settings Restart and Update
- Add warning in call.edit(), if message was sent w\o buttons, ergo Telegram won't allow to edit this message
- Add --force restart
- Add ability to customize .info (this is only your problem, if you break something)
- Properly censor known tokens in logs
- Replace regex check in utils.check_url() with urllib parser

## 🌑 Heroku 1.1.12

- Consider avoiding redundant requests to TG API in order to get the client id and rather using self.\_tg_id, which is now available for all modules

## 🌑 Heroku 1.1.11

- Add fast uploader (self.fast_upload, self.fast_download)
- Fix translations

## 🌑 Heroku 1.1.10

- Add ability to download modules from many additional repos (e.g. you can download weather by morisummer via just .dlmod weather, and also list all available repos via .dlmod)

## 🌑 Heroku 1.1.9

- Fix \_generate_markup in order that it automatically sets up callback hooks to \_custom_map if callback was passed in buttons
- Add switch_inline_query and switch_inline_query_current_chat parsers
- Fix minor issues

## 🌑 Heroku 1.1.8

- Stuff, related to translation issues
- Add self.get_prefix() to all modules, which returns current command prefix
- Add possibility to silently self-unload mod, e.g if some condition is not matched. Usecase can be found in modules/okteto.py
- Add async def on_dlmod(self, client: "TelegramClient", db: "database.Database") handling. This can be e.g. used to subscribe to module's author's channel
- Rework Okteto Pinger, so it removes messages, if userbot is installed on other platform and so it even works
- Add trusted developers to quickstart message
- Automatically switch language via quickstart message button

## 🌑 Heroku 1.1.7

- Add self.animate function to all modules, which allows you to easily create fancy animations

## 🌑 Heroku 1.1.6

- Allow and process callback field in result of inline query answer. You can also use this in your own functions. Simply pass prepare_callbacks=True to \_generate_markup
- Generate InlineCall object on \_custom_map handlers

## 🌑 Heroku 1.1.5

- Minor update: Allow passing disable_security and always_allow to buttons directly

## 🌑 Heroku 1.1.4

- Ability to set inline bot username on setup (in web interface)
- Fix inline help
- Add more debug info to logs
- Add attribute status to loops
- Fix HerokuDL link parsing
- Suggest enabling value in bounding mask if it is not
- Mask tokens in logs
- Add utils.get_git_hash()
- Add debugging mode for developers

## 🌑 Heroku 1.1.3

- Finally (hopefully) fix config
- Minor bug fixes related to inline form processing

## 🌑 Heroku 1.1.2

- Add @loader.loop, which provides developers access to easy-to-make infinite loops. Wait for developers docs to update for more info

## 🌑 Heroku 1.1.1

- Drop Uniborg and Raphielgang compatibility layer. More info in [2d525ab](https://github.com/hikariatama/Heroku/commit/2d525ab6b0e6b9d7ccd7408bbe175cea24d780a5)
- Minor bug fixes

## 🌑 Heroku 1.1.0

- Make inline commands' docstrings translatable
- Introducing HerokuDynamicTranslate - the possibility for developers to translate their own modules to other language without usage of native translates
- Rework translates system, because «translate channels wut¿». Now translate pack can be loaded from disk or from web
- Add utils.check_url
- Get rid of babel
- Add IP address and possible cities to web auth popup
- Add web auth popup ratelimit
- Automatically delete web auth flow when timeout's exceeded
- Adapt core modules so they send plain text message, if unable to send inline
- New type: InlineMessage
- Rework type InlineCall
- Make it so the forms, lists and galleries return editable InlineMessage
- Return a single answerable value from utils.answer, not a list
- Ensure that inline unit is actually being unloaded
- Refactor inline - remove redundant arguments, rename some core methods
- Fix userbot crash when using galleries' slideshow for a long time
- Rework slideshow so it runs in the background
- Fix here, fix there, fix somewhere...

## 🌑 Heroku 1.0.29

- Add option to control inline and callback handlers' security via loader decorators, including brand new @loader.inline_everyone
- Refactor HerokuSecurity, especially the bounding mask control

## 🌑 Heroku 1.0.28

- Add silent param to inline.form, inline.gallery, inline.list
- Add photo param to inline.form
- Add URL validator to inline.\_generate_markup
- Ignore MessageIdInvalidError in .e

## 🌑 Heroku 1.0.27

Thankfully to @bsolute, now we have a cool smart_split in utils. The messages are split without loosing formatting and emojies, preferably on line breakes / spaces.

## 🌑 Heroku 1.0.26

- Add utils.smart_split which splits message in chunks of chunk_size, keeping parse_mode and entities in a right way (relocates 'em)
- If response of utils.answer is too big to be sent in one particular message, it will be split in chunks of 4096 and sent via inline.list

## 🌑 Heroku 1.0.25

- Add disable_security to inline forms, lists and galleries

## 🌑 Heroku 1.0.24

- Okteto fixes (persistent uri, fix webpage)
- Add utils.dnd, which allows to mute and archive peer
- Security fixes for groups (not super\mega groups)
- Minor bug fixes

## 🌑 Heroku 1.0.23

- Add ability to disable HerokuDL natively
- Fix Updater so it works if you have troubles with inline mode

## 🌑 Heroku 1.0.22

Add HerokuDL module to use inline download buttons in verified channels

## 🌑 Heroku 1.0.21

A lot of stuff: web fixes, bug fixes, automatic seamless userbot restart when adding new account in web, replace emojies, add inline list feature, fix types name conflict and I don't remember other fixes, read code

## 🌑 Heroku 1.0.20

- Allow passing reply_markup field to InlineQuery's result
- Refactor reply markup parser so it accepts more formats of inline markup

## 🌑 Heroku 1.0.19

- Allow developers to pass InlineQuery result via return operator in inline handlers. Read the docs for more info
- Move query_gallery to a separate module

## 🌑 Heroku 1.0.18

- Add silent and archive params to utils.asset_channel.
- Remake logging so it become native with `BotLogger`.
- Inject `BotLogger` analog directly

## 🌑 Heroku 1.0.17

- Add ability to set up inline commands' security map (only `owner`, `sudo`, `support` and `everyone`, because other permissions are inaccessible when processing inline query).
- Add database serializeability check to avoid JSON-serialization problems if unserializable object is being stored in db.
- Minor bugfixes

## 🌑 Heroku 1.0.16

- Full support of Okteto cloud deployment inculding persistent data storage (additional volume is created)
- Fix automatic waker for container

## 🌑 Heroku 1.0.15

- Add more errors to query aka query.e500()

## 🌑 Heroku 1.0.14

- Add gallery slideshow

## 🌑 Heroku 1.0.13

- Include command prefix in inline info.
- Fix --no-web.
- Suggest to save modules to filesystem

## 🌑 Heroku 1.0.12

- Optimize forms, galleries and custom_map storage by ommiting keys with default values and dynamically generate them.
- Add feature to inherit command-caller permissions on form and gallery (crutchy).
- Minor improvements and bug fixes

## 🌑 Heroku 1.0.11

- Add inline.query_gallery to add ability to call inline gallery via inline query.
- Add `e404` attribute to `InlineQuery`, which should be shown, that no results were found

## 🌑 Heroku 1.0.10

- Add feature to send gifs in inline galleries (gif param).
- Make argument `caption` of inline gallery not mandatory

## 🌑 Heroku 1.0.9

- Full inline structure rework.
- Split this madness into separate modules (`InlineUnit`s), which extend the main unit - `InlineManager`.
- Compatibility layer is not main priority.

## 🌑 Heroku 1.0.8

- Code refactoring
- Minor bug fixes
- Rewrite security

## 🌑 Heroku 1.0.7

- Massive inline galleries update, memoization, back button, preloading and other features.
- Fix some minor bugs, add `ascii_face` to utils

## 🌑 Heroku 1.0.6

- Add welcome message, triggered when userbot is installed

## 🌑 Heroku 1.0.5

- Add gallery memoization (ability to close gallery and scroll it back)

## 🌑 Heroku 1.0.4

- Add Okteto pinger, which will wake the pod up, when it goes to sleep

## 🌑 Heroku 1.0.3

- Fix a lot of stuff in web
- Add new features to web
- Merge root and initial_root
- Remove trailing whitespaces

## 🌑 Heroku 1.0.2

- Full restructure of core code
- Refactor web
- Create new active bg

## 🌑 Heroku 1.0.1

- Drop heroku support
- Remove redundant code
- Remake badge
- Remake installer
