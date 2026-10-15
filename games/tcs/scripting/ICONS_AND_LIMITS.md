# Native portraits, capacities and resource lifetime

[Guide index](README.md) · [Character authoring](CHARACTERS.md)

## Portrait identity and resource lookup

The character's `icon` value identifies the portrait objects. The native
registration path uses a name and a companion name with `1` appended. An
illustrative declaration is:

```text
icon="workshop_knight_icon"
```

For that name, inspect objects `workshop_knight_icon` and
`workshop_knight_icon1` in the appropriate scene. A plausible filename alone
does not supply the objects, materials and geometry required by the UI.

Native individual resources follow the observed form
`STUFF/ICONS/<icon-name>_PC.GSC`. Main aggregate icon scenes can supply many
portraits together. These GSCs are binary assets, not SCP programs, and the
character TXT names an object/resource identity rather than a source image.

## `icons_all` and multi-portrait scenes

A scene can contain multiple portrait objects. Loading it makes those objects
available within its native registration/ownership context. Calling a new file
`something_icons_all` does not by itself establish automatic discovery at
startup, nor does placing it on disk prove every menu will load it.

The practical distinction is between **the object exists in a file** and
**the owning scene has been loaded and bound for this UI context**. A character
loaded in the cantina can cause assets to become available that were absent
from an earlier selector. Do not treat that incidental availability as proof
of a reliable aggregate-loading route.

For native-only packs, ensure that the required portraits are supplied by the
aggregate/resources actually used in the target menu. Test without first
loading the character elsewhere. This guide does not promise that a carrier
character's second bundle automatically replaces individual icon loads for
every other character.

Native scene ownership also matters: keeping an icon name registered is not
the same as keeping its backing hierarchy alive after area teardown.

## Three different UI failures

| Visible result | First distinction to check |
| --- | --- |
| Question mark / unavailable selection | Unlock or availability state before diagnosing the portrait |
| Empty frame for an available character | Missing pair, scene not loaded, failed registration or invalid backing resource |
| Portrait appears only after meeting/loading a character | Context-dependent loading or cached resource availability |

Check shop, Free Play grid, HUD and loading screen separately. Each successful
view proves only that view and loading sequence. A name appearing correctly
does not establish portrait availability; text localization is separate.

## Independent native limits

These are findings for the analyzed PC build, not universal values for all
editions. They describe different structures and must not be combined into
one advertised “character limit.” No TXT recipe to enlarge them is established.

| Native structure | Observed capacity | Practical consequence |
| --- | --- | --- |
| Character definition registry | 340 definitions | Registrations include more than the visible playable roster |
| Character parser hard maximum | 500 | Does not override the smaller runtime registry |
| Shop character records | 100 | Appending collection entries does not guarantee more shop records |
| Shop purchase bitfield | 128 bits | Storage width is not proof the 100-record shop supports 128 entries |
| Shared render-name registry | 750 entries | Shared with non-portrait names; often two names per portrait |
| Shared name-text storage | 10,000 bytes | Long or numerous names also consume a separate byte budget |
| Registered hierarchy pointers | 256 | More object names do not create more scene/hierarchy ownership capacity |
| Resident character model/skin cache | 48 slots | Installed definition count is not resident model capacity |
| Animation filename cache | 1,024 records | Shared animation filenames have a separate exhaustion mode |
| Party slots | 8 | Does not mean eight arbitrary new party members can be added by script |
| Native saved character availability | 340 bytes | More text registrations do not create more persistent availability storage |
| Stock saber selections | 4 | New color words do not extend the native palette |
| Customizer weapon choices | 9 | Does not imply nine saber colors or automatic discovery of new weapons |

The hierarchy count is not the number of mesh objects in one hierarchy. The
render-name registry is not a dedicated portrait count. In particular, dividing
750 by two does not yield a usable “375 character icons” guarantee because
other registered names and text storage also consume resources.

These bounds were identified through native analysis and targeted research.
They are not a fresh clean-install stress test performed for this documentation.
Parser and allocation bounds should be checked against the actual executable
revision before relying on them for tooling.

## Animation-cache exhaustion

Native filename records occupy 52 bytes: 48 bytes of name storage plus a
resource pointer. This structure size is not a recommendation to use 47-character
paths without checking all preceding name/path handling.

The loose-animation path at `0x0062D400` and bundled registration path at
`0x0062D360` check loaded count against capacity and return null at exhaustion.
Filename reuse is case-insensitive on the inspected loose path. Sharing a
resource name may avoid another record; renaming copies unnecessarily can
consume more records even when the payloads are identical.

The loader can therefore produce a model with some working animations and
missing locomotion. Diagnose null/missing animation resources separately from
model-cache exhaustion or an unsupported action ID. Native level reset at
`0x00547780` restores counts to the permanent-resource baseline; availability
in one area does not prove an unlimited lifetime cache.

## Performance and resource lifetime

Registering text definitions, loading models and uploading textures are
different costs. Native character loading can perform synchronous work; adding
many distinct animations and textures can increase loading pauses even while
remaining within nominal entry counts.

Native background behaviour can preload unlocked characters. A cache may fill
before the author explicitly selects every character. This guide provides no
native TXT switch to disable that behaviour.

For native content packs, reuse genuinely compatible resources, avoid duplicate
filenames for identical animations, keep icon loading predictable and test
repeated area transitions. Do not remove required animations or collapse
different rigs just to reduce a count. Runtime arenas, RAM and GPU resources
remain constraints even when a particular table has room.

See [research evidence](RESEARCH.md) for build identification and native
addresses. Enlarging these structures or changing save layouts is outside
native text authoring.
