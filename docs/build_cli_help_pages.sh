#!/bin/bash

# TODO / Possibility: Integrate rich-click into boardwalk/boardwalkd directly,
# so this workaround isn't needed to generate a pretty help text.

commands=(
    "boardwalk"
    "boardwalk catch"
    "boardwalk check"
    "boardwalk init"
    "boardwalk login"
    "boardwalk release"
    "boardwalk run"
    "boardwalk version"
    "boardwalk workspace"
    "boardwalk workspace dump"
    "boardwalk workspace list"
    "boardwalk workspace reset"
    "boardwalk workspace show"
    "boardwalk workspace use"

    "boardwalkd"
    "boardwalkd serve"
    "boardwalkd version"
)

OUTPUT_WIDTH_COLUMMNS=110

GET_PAGE_NAME() {
    echo '`'"$1"'`'
}

for cmd in "${commands[@]}"; do
    # Define regular expression patterns for 'boardwalk' and 'boardwalkd', so we
    # can sort them into the correct subdirectories. Note that we need to use
    # POSIX-compliant EREs, here, since this is portable between MacOS/Linux.
    # See: https://stackoverflow.com/a/12696899
    # This is, effectively, '\bboardwalk\b' and '\bboardwalkd\b'
    BOARDWALK_REGEX="^[[:<:]]boardwalk[[:>:]]"
    BOARDWALKD_REGEX="^[[:<:]]boardwalkd[[:>:]]"
    if [[ $cmd =~ $BOARDWALK_REGEX ]]; then
        SUBDIR=boardwalk
    elif [[ $cmd =~ $BOARDWALKD_REGEX ]]; then
        SUBDIR=boardwalkd
    else
        # Don't assume if we cannot correctly parse the command being generated
        echo "[!] Skipping generation for $cmd; is this a boardwalk or boardwalkd command?"
        continue
    fi
    FILENAME=./source/cli_helpdocs/$SUBDIR/$(echo "$cmd" | tr ' ' _).md
    echo "[+] Generating doc page for $FILENAME"
    {
        echo "# $(GET_PAGE_NAME "$cmd")"
        echo ""
        echo '<div class="full-width" id="cmd-help-text">'
        echo '<pre>'
        # shellcheck disable=SC2086  # We actually want word splitting, here
        COLUMNS=$OUTPUT_WIDTH_COLUMMNS rich-click --output html $cmd --help
        echo '</pre>'
        echo '</div>'
        echo ''
    }  > "$FILENAME"
done
