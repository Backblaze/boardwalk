"""
Contains functions to handle Slack command handling
"""

import re
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from importlib.metadata import metadata as lib_metadata
from importlib.metadata import version as lib_version
from typing import Any

from loguru import logger
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncAck, AsyncApp, AsyncBoltContext
from slack_bolt.response import BoltResponse
from slack_sdk.errors import SlackApiError
from slack_sdk.models.blocks import (
    ActionsBlock,
    AlertBlock,
    ButtonElement,
    ContextBlock,
    ConversationSelectElement,
    DividerBlock,
    ImageElement,
    InputBlock,
    MarkdownTextObject,
    Option,
    OverflowMenuElement,
    PlainTextObject,
    RichTextBlock,
    RichTextPreformattedElement,
    RichTextSectionElement,
    SectionBlock,
    StaticMultiSelectElement,
    StaticSelectElement,
)
from slack_sdk.models.views import View
from slack_sdk.web.async_client import AsyncWebClient

from boardwalkd.protocol import WorkspaceEvent
from boardwalkd.server import SERVER_URL, SLACK_SLASH_COMMAND_PREFIX, SLACK_TOKENS, internal_workspace_event
from boardwalkd.server import state as STATE
from boardwalkd.utils import count_of_workspaces_caught, list_active_workspaces, list_inactive_workspaces

app = AsyncApp(token=SLACK_TOKENS.get("bot"))


async def middleware_verify_authorized_boardwalk_user(
    ack: AsyncAck,
    action: dict[str, Any] | None,
    command: dict[str, Any] | None,
    body: dict[str, Any],
    client: AsyncWebClient,
    context: AsyncBoltContext,
    next: Callable[[], Awaitable[BoltResponse]],
    # payload: dict[str, Any],
):
    """Middleware for Slack app functions to verify if a given user has authenticated to Boardwalk.

    Authentication depends on the user's email presented to Boardwalk and Slack to match.
    """
    slack_user_id = context.get("user_id", "")
    trigger_id = body.get("trigger_id", "")
    slack_user_profile = await client.users_info(user=slack_user_id)
    slack_user_email = slack_user_profile.get("user", {}).get("profile", {}).get("email")
    if slack_user_email in STATE.users.keys():
        context["boardwalk_user_email"] = slack_user_email
        return await next()
    else:
        await ack()
        if command is not None and "command" in command:
            attempted_action = {"type": "command", "command": command["command"]}
        elif action is not None and "action_id" in action:
            attempted_action = {"type": "action", "action_id": action["action_id"]}
        failure_info = {
            "attempted_action": attempted_action,
            "slack_user_id": slack_user_id,
            "slack_user_email": slack_user_email,
        }
        if trigger_id:
            logger.warning(f"Not processing request from user due to missing authentication: {failure_info}")
            auth_fail_msg = [
                f"Apologies, <@{slack_user_id}>, however the email associated with your Slack account -- {slack_user_email} -- does not exist within the Boardwalk's user list, and thus, are not allowed to perform that action.",
                f"You will need to visit the Boardwalk Dashboard at {SERVER_URL}, and log in to authenticate.",
            ]
            modal_view = View(
                title="Authentication Required",
                type="modal",
                callback_id="action_dummy_slack_acknowledgement_handler",
                close=PlainTextObject(text="Close"),
                blocks=[
                    AlertBlock(
                        level="error",
                        text=MarkdownTextObject(text="Boardwalk authentication required for this action"),
                    ),
                    SectionBlock(text=MarkdownTextObject(text="\n\n".join(auth_fail_msg))),
                ],
            )
            await client.views_open(trigger_id=trigger_id, view=modal_view)
        return BoltResponse(status=200, body="")


@app.command(f"/{SLACK_SLASH_COMMAND_PREFIX}-version")
async def hello_command(ack: AsyncAck, body: dict[str, Any], client: AsyncWebClient) -> None:
    await ack()
    await client.chat_postEphemeral(
        channel=body["channel_id"],
        user=body["user_id"],
        text=f"Heya, <@{body['user_id']}>! The version of Boardwalk (`boardwalkd`) that I am running is {lib_version('boardwalk')}!",
    )


@app.command(f"/{SLACK_SLASH_COMMAND_PREFIX}-catch-release", middleware=[middleware_verify_authorized_boardwalk_user])
@app.action("action_catch_or_release_workspace", middleware=[middleware_verify_authorized_boardwalk_user])
async def catch_release_workspaces(ack: AsyncAck, body: dict[str, Any], client: AsyncWebClient):
    """
    Opens a view prompting if the user wants to catch/release all, or a subset of workspaces.
    """
    await ack()

    # Construct the list of workspaces that we need to pass to the view (maximum of 100 items)
    workspaces: Sequence[Option] = [Option(value="**all_workspaces**", text="**ALL WORKSPACES**")]
    workspaces.extend([Option(value=workspace, text=workspace[0:74]) for workspace in sorted(STATE.workspaces.keys())][0:99])

    modal_catch_release = View(
        type="modal",
        callback_id="modal_catch_release",
        title=PlainTextObject(text="Boardwalk Catch/Release"),
        submit=PlainTextObject(text="Submit"),
        close=PlainTextObject(text="Cancel"),
        blocks=[
            SectionBlock(
                text=MarkdownTextObject(
                    text=f"💡 It's a wise idea to check the <{SERVER_URL}|Boardwalk Dashboard> before catching or releasing workspaces!"
                )
            ),
            DividerBlock(),
            InputBlock(
                block_id="workspace_action",
                label=PlainTextObject(text="Select whether to catch or release workspace(s)"),
                optional=False,
                element=StaticSelectElement(
                    action_id="action",
                    placeholder="Select one...",
                    options=[
                        Option(value="catch", text="Catch workspace(s)"),
                        Option(value="release", text="Release workspace(s)"),
                    ],
                ),
            ),
            InputBlock(
                block_id="workspace_targets",
                label=PlainTextObject(text="Select all workspaces, or select workspace(s)"),
                element=StaticMultiSelectElement(
                    action_id="workspaces", placeholder="Select target workspace(s)...", options=workspaces
                ),
            ),
            ContextBlock(
                elements=[MarkdownTextObject(text="The displayed targets are limited to 100 items displayed in total.")]
            ),
            DividerBlock(),
            SectionBlock(
                block_id="status_block",
                text=MarkdownTextObject(
                    text="Where to send a confirmation message once the selected action has been taken"
                ),
                accessory=ConversationSelectElement(
                    action_id="data",
                    default_to_current_conversation=True,
                ),
            ),
            ContextBlock(
                elements=[MarkdownTextObject(text="No need to modify this; your current channel is auto-populated.")]
            ),
            DividerBlock(),
            SectionBlock(
                text=MarkdownTextObject(
                    text=" ".join(  # semgrep avoidance https://sg.run/Kl07 -- string-concat-in-list
                        [
                            "*Note*: It should go without saying that you should exercise caution prior to catching or",
                            "releasing workspaces. Dragons might be lurking. 🐉",
                        ]
                    ),
                )
            ),
        ],
    )

    # Display the modal to the calling client
    await client.views_open(trigger_id=body["trigger_id"], view=modal_catch_release)


@app.view("modal_catch_release", middleware=[middleware_verify_authorized_boardwalk_user])
async def modal_catch_release_view_submission_event(
    ack: AsyncAck, client: AsyncWebClient, context: AsyncBoltContext, payload: dict[str, Any]
):
    """
    Process the user's response to the catch/release modal generated from catch_release_workspaces().
    """
    await ack()

    # String: `catch` or `release`
    action: str = payload["state"]["values"]["workspace_action"]["action"]["selected_option"]["value"]
    target_workspaces_dict_list: list[dict] = payload["state"]["values"]["workspace_targets"]["workspaces"][
        "selected_options"
    ]
    # List: ['**all_workspaces**', 'workspace_name', ...]
    workspaces_str_list: list[str] = [item["value"] for item in target_workspaces_dict_list]
    conversation_id: str = payload["state"]["values"]["status_block"]["data"]["selected_conversation"]

    if "**all_workspaces**" in workspaces_str_list:
        workspaces = STATE.workspaces.keys()
    else:
        workspaces = workspaces_str_list

    rejected_workspaces = set(workspaces) - set(STATE.workspaces.keys())
    _actioned_workspaces: list[str] = []
    for workspace in workspaces:
        if workspace not in rejected_workspaces:
            STATE.workspaces[workspace].semaphores.caught = True if action == "catch" else False
            # Record who caught the workspace(s)
            event = WorkspaceEvent(
                severity="info",
                message=f"Workspace {'caught' if action == 'catch' else 'released'} by {context['boardwalk_user_email']} via Slack",
            )
            internal_workspace_event(workspace, event)
            _actioned_workspaces.append(workspace)
        else:
            logger.warning(
                f"Not processing {action} for workspace named {workspace} from {context['boardwalk_user_email']} as workspace does not exist"
            )
    STATE.flush()

    if len(_actioned_workspaces) > 0:
        message_blocks = [
            SectionBlock(
                text=MarkdownTextObject(
                    text=" ".join(  # semgrep avoidance https://sg.run/Kl07 -- string-concat-in-list
                        [
                            f"Heya, <@{context['user_id']}>! As requested, the following workspace(s) have been",
                            f"*{'caught' if action == 'catch' else 'released'}*. As always, you can view the Boardwalk",
                            f"Dashboard at {SERVER_URL} for an up-to-the-moment status!",
                        ]
                    )
                )
            ),
            RichTextBlock(
                elements=[
                    RichTextPreformattedElement(
                        elements=[
                            {
                                "type": "text",
                                "text": ", ".join(sorted(_actioned_workspaces)),
                            }
                        ]
                    )
                ]
            ),
        ]
    else:
        message_blocks = [
            SectionBlock(
                text=MarkdownTextObject(
                    text=f"Well, that's peculiar. No workspaces were actioned. Try again, perhaps, or use the Boardwalk Dashboard at {SERVER_URL}."
                )
            )
        ]

    try:  # Attempt to send an ephemeral confirmation
        await client.chat_postEphemeral(
            channel=conversation_id,
            user=context["user_id"],
            blocks=message_blocks,
            text=f"Workspace(s) {action} successfully!",
        )
    except SlackApiError as e:
        if e.response["error"] == "user_not_in_channel":  # User probably is on the Home tab of the App; send it in DM.
            _response = await client.conversations_open(users=context["user_id"])
            await client.chat_postMessage(
                channel=_response["channel"]["id"],  # pyright: ignore[reportOptionalSubscript]
                user=context["user_id"],
                blocks=message_blocks,
                text=f"Workspace(s) {action} successfully!",
            )
        else:  # Reraise.
            raise e


@app.command(f"/{SLACK_SLASH_COMMAND_PREFIX}-list")
async def command_list_active_workspaces(ack: AsyncAck, body: dict[str, Any], client: AsyncWebClient) -> None:
    """
    Lists workspaces with a connected CLI runner.
    """
    await ack()

    message_blocks = [
        SectionBlock(text=MarkdownTextObject(text="The following workspaces have an active worker connected:"))
    ]
    active_workspaces = list_active_workspaces()

    if len(active_workspaces) > 0:
        message_blocks.append(SectionBlock(text=MarkdownTextObject(text=", ".join(active_workspaces))))
        await client.chat_postEphemeral(
            channel=body["channel_id"], user=body["user_id"], blocks=message_blocks, text="Active workspaces list"
        )
    else:
        await client.chat_postEphemeral(
            channel=body["channel_id"], user=body["user_id"], text="There are no currently active workspaces!"
        )


@app.event("app_home_opened")
@app.action("action_open_app_home")
@app.action("action_refresh_workspaces")
async def app_home_opened(ack: AsyncAck, client: AsyncWebClient, context: AsyncBoltContext):
    await ack()
    logger.trace("App home opened")

    app_home_view = View(
        type="home",
    )
    app_home_blocks = [
        SectionBlock(
            text="*Welcome to the Boardwalk Slack App Home!*",
            accessory=OverflowMenuElement(
                action_id="action_app_home_overflow_menu_event_handler",
                options=[
                    Option(
                        text="Source code",
                        url=lib_metadata("boardwalk").get(name="Home-Page"),
                        value="app_home_overflow_view_source_repository",
                    ),
                    Option(text="About Boardwalk", value="app_home_overflow_about_boardwalk"),
                ],
            ),
        ),
        ActionsBlock(
            elements=[
                ButtonElement(text="Refresh :recycle:", action_id="action_refresh_workspaces", style="primary"),
                ButtonElement(text="Catch/Release Workspace", action_id="action_catch_or_release_workspace"),
                ButtonElement(
                    text="Dashboard :link:", url=SERVER_URL, action_id="action_dummy_slack_acknowledgement_handler"
                ),
                ButtonElement(
                    text="Workspace Details :microscope:", action_id="action_display_workspace_details_app_home"
                ),
            ]
        ),
        DividerBlock(),
        SectionBlock(
            text=MarkdownTextObject(
                text="*Legend*: :female-detective: Check mode  /  :athletic_shoe: Run mode  /  :fishing_pole_and_fish: Workspace caught"
            )
        ),
        ContextBlock(
            elements=[
                MarkdownTextObject(
                    text=f"*Note*: The data shown below was last refreshed at *{datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')} (UTC)*."
                ),
            ]
        ),
        DividerBlock(),
        SectionBlock(
            text=" ".join(  # semgrep avoidance https://sg.run/Kl07 -- string-concat-in-list
                [
                    f"There are {len(STATE.workspaces)} workspaces in total, of which {count_of_workspaces_caught()} are",
                    f"caught, with {len(list_active_workspaces())} active CLI workers.",
                ]
            )
        ),
        DividerBlock(),
    ]

    _active: list[str] = []
    _inactive: list[str] = []
    for _list, _workspaces in [(_active, list_active_workspaces()), (_inactive, list_inactive_workspaces())]:
        for _workspace in _workspaces:
            _list.append(
                f"{'🕵️‍♀️' if STATE.workspaces[_workspace].details.worker_command == 'check' else '👟'}"
                f"{'🎣' if STATE.workspaces[_workspace].semaphores.caught else ''} {_workspace}"
            )

    app_home_blocks.extend(
        [
            SectionBlock(text=MarkdownTextObject(text="*Active workspaces*")),
            RichTextBlock(
                elements=[
                    RichTextSectionElement(
                        elements=[
                            {
                                "type": "text",
                                "text": "\n\n".join(
                                    _active if _active else ["There are no currently active workspaces."]
                                ),
                            }
                        ]
                    )
                ]
            ),
            DividerBlock(),
            SectionBlock(text=MarkdownTextObject(text="*Inactive workspaces*")),
            RichTextBlock(
                elements=[
                    RichTextSectionElement(
                        elements=[
                            {
                                "type": "text",
                                "text": "\n\n".join(
                                    _inactive if _inactive else ["There are no currently inactive workspaces."]
                                ),
                            }
                        ]
                    )
                ]
            ),
            DividerBlock(),
        ]
    )

    app_home_view.blocks = app_home_blocks
    await client.views_publish(user_id=context["user_id"], view=app_home_view)


@app.action(re.compile("action_display_workspace_details_app_home(_refresh)?"))
async def app_home_workspace_details(
    ack: AsyncAck,
    client: AsyncWebClient,
    context: AsyncBoltContext,
    payload: dict[str, Any],
) -> None:
    logger.trace("Entered app home workspace details")
    await ack()

    _target_workspace: str | None = None

    # The user interacted with one of the items in the ActionsBlock
    if payload is not None:
        # The user selected an item in the workspace dropdown
        if _target_workspace := payload.get("selected_option", {}).get("value", None) if not None else None:
            if not STATE.workspaces.get(_target_workspace):
                _target_workspace = None
        # The user clicked the Refresh workspace details button
        elif _target_workspace := payload.get("value") if not None else None:
            pass

    if _target_workspace_details := STATE.workspaces.get("" if _target_workspace is None else _target_workspace):
        logger.info(f"Retrieving workspace details for {_target_workspace}")
        _workspace_event_details: list[str] = [
            " - ".join(
                [
                    f"{event.create_time.replace(microsecond=0).strftime('%Y-%m-%d %H:%M:%S (UTC)')}",  # type: ignore
                    f"{event.severity}",
                    f"{event.message}",
                ]
            )
            for event in reversed(_target_workspace_details.events)
        ]
        _workspace_details_rich_text_block = RichTextBlock(
            elements=[
                RichTextSectionElement(
                    elements=[
                        {"type": "text", "text": f"{detail_type}: ", "style": {"bold": True}},
                        {"type": "text", "text": f"{detail_value}"},
                    ]
                )
                for detail_type, detail_value in {
                    "Workspace": _target_workspace,
                    "Workflow": _target_workspace_details.details.workflow,
                    "Worker": f"{_target_workspace_details.details.worker_username}@{_target_workspace_details.details.worker_hostname}",
                    "Host Pattern": _target_workspace_details.details.host_pattern,
                    "Command": _target_workspace_details.details.worker_command,
                    "Last Seen": _target_workspace_details.last_seen,
                }.items()
            ]
        )
    else:
        _workspace_event_details: list[str] = ["No details to show. Perhaps select a workspace?"]

    app_home_view = View(
        type="home",
    )
    app_home_blocks = [
        SectionBlock(
            text="*Boardwalk Workspace Details*",
            accessory=ButtonElement(text="🏡 Go home", action_id="action_open_app_home", style="primary"),
        ),
        ActionsBlock(
            elements=[
                StaticSelectElement(
                    action_id="action_display_workspace_details_app_home",
                    placeholder="Select a workspace...",
                    initial_option=Option(value=_target_workspace, text=_target_workspace[0:74])
                    if _target_workspace
                    else None,
                    options=[Option(value=name, text=name[0:74]) for name in sorted(STATE.workspaces.keys())]
                    if len(STATE.workspaces) >= 1
                    else [Option(value="__NO_WORKSPACES_AVAILABLE", text="--- No workspaces ---")],
                ),
                ButtonElement(
                    text="Refresh workspace details",
                    style="primary",
                    value=_target_workspace,
                    action_id="action_display_workspace_details_app_home_refresh",
                ),
            ]
        ),
        ContextBlock(
            elements=[
                MarkdownTextObject(
                    text=f"The information shown was last refreshed at {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')} (UTC)."
                ),
            ]
        ),
        DividerBlock(),
    ]
    if _target_workspace:
        app_home_blocks.append(_workspace_details_rich_text_block)
        _semaphores = STATE.workspaces.get(_target_workspace).semaphores  # pyright: ignore[reportOptionalMemberAccess]
        app_home_blocks.extend(
            [
                SectionBlock(
                    text=f"This workspace is {'*' if _semaphores.caught else '*not'} caught* on the `boardwalkd` server."
                ),
                SectionBlock(
                    text=f"A `boardwalk` worker {'*does*' if _semaphores.has_mutex else '*does not*'} hold a server-side mutex for this workspace."
                ),
            ]
        )
        if _target_workspace_details.details.deployment_url:  # pyright: ignore[reportOptionalMemberAccess]
            app_home_blocks.extend(
                [
                    DividerBlock(),
                    SectionBlock(
                        text=f"The *`boardwalk` Worker Log* is available at: {_target_workspace_details.details.deployment_url}"  # pyright: ignore[reportOptionalMemberAccess]
                    ),
                ]
            )
        app_home_blocks.extend([SectionBlock(text="*Server Event Log*"), DividerBlock()])

    app_home_blocks.extend(
        [
            RichTextBlock(
                elements=[
                    RichTextSectionElement(elements=[{"type": "text", "text": "\n\n".join(_workspace_event_details)}])
                ]
            ),
            DividerBlock(),
        ]
    )

    app_home_view.blocks = app_home_blocks
    await client.views_publish(user_id=context["user_id"], view=app_home_view)


async def _modal_about_boardwalk(trigger_id: str, client: AsyncWebClient):
    """
    Displays the About Boardwalk modal view
    """
    _about_data = [
        "*Boardwalk*: A linear <https://github.com/ansible/ansible|Ansible> workflow engine.",
        f"Version: {lib_version('boardwalk')}",
        "",
        f"Server URL: {SERVER_URL}",
        "Source code: <https://github.com/Backblaze/boardwalk/|GitHub>",
        "Licensed under: The MIT License",
        "Developed at: <https://www.backblaze.com/|Backblaze, Inc.>",
        "Developed by: <https://github.com/m4wh6k|Mat Hornbeek>",
        "Maintained by: Kiera Phoenix",
    ]
    modal_view = View(
        type="modal",
        callback_id="action_dummy_slack_acknowledgement_handler",
        title=PlainTextObject(text="About Boardwalk"),
        close=PlainTextObject(text="Close"),
        blocks=[
            SectionBlock(
                text=MarkdownTextObject(text="\n".join(_about_data)),
                accessory=ImageElement(
                    alt_text="An image of a boardwalk",
                    image_url="https://f004.backblazeb2.com/file/BoardwalkBLZE/boardwalk_icon.jpg",
                ),
            ),
        ],
    )
    await client.views_open(trigger_id=trigger_id, view=modal_view)


@app.action("action_app_home_overflow_menu_event_handler")
async def action_app_home_overflow_menu_event_handler(
    ack: AsyncAck, body: dict[str, Any], client: AsyncWebClient, payload: dict[str, Any]
) -> None:
    await ack()
    _option: str = payload["selected_option"].get("value")

    if _option == "app_home_overflow_view_source_repository":
        return
    elif _option == "app_home_overflow_about_boardwalk":
        await _modal_about_boardwalk(trigger_id=body["trigger_id"], client=client)


@app.action("action_dummy_slack_acknowledgement_handler")
async def dummy_slack_acknowledgement_handler(ack: AsyncAck):
    """
    Slack _requires_ an acknowledgement to certain actions, but some things--like opening an external application
    shouldn't require one. This is that dummy handler to appease Slack.
    """
    await ack()


async def connect() -> None:
    handler = AsyncSocketModeHandler(app=app, app_token=SLACK_TOKENS.get("app"))
    await handler.connect_async()
