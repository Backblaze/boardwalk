# `boardwalk init`

<div class="full-width" id="cmd-help-text">
<pre>

                                                                                                              
 <span style="color: #808000; text-decoration-color: #808000">Usage:</span> <span style="font-weight: bold">boardwalk init</span> [<span style="color: #008080; text-decoration-color: #008080; font-weight: bold">OPTIONS</span>]                                                                              
                                                                                                              
 Inits the workspace state with host data. Gathers Ansible facts for hosts matching the workspaces host       
 pattern. OK to run multiple times; hosts are only added or updated, never removed by this operation. Use     
 `boardwalk workspace reset` to clear existing state if needed                                                
                                                                                                              
<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────────────╮</span>
<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">│</span> <span style="color: #008080; text-decoration-color: #008080; font-weight: bold">--limit</span>             <span style="color: #008000; text-decoration-color: #008000; font-weight: bold">-l</span>      <span style="color: #808000; text-decoration-color: #808000; font-weight: bold">TEXT</span>  An Ansible pattern to limit hosts by. Defaults to no limit               <span style="color: #7f7f7f; text-decoration-color: #7f7f7f">│</span>
<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">│</span> <span style="color: #008080; text-decoration-color: #008080; font-weight: bold">--retry</span>/<span style="color: #008080; text-decoration-color: #008080; font-weight: bold">--no-retry</span>  <span style="color: #008000; text-decoration-color: #008000; font-weight: bold">-r</span>/<span style="color: #008000; text-decoration-color: #008000; font-weight: bold">-nr</span>  <span style="color: #808000; text-decoration-color: #808000; font-weight: bold">    </span>  Retry getting state for hosts that were unreachable/failed on the last   <span style="color: #7f7f7f; text-decoration-color: #7f7f7f">│</span>
<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">│</span>                                   attempt                                                                  <span style="color: #7f7f7f; text-decoration-color: #7f7f7f">│</span>
<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">│</span>                                   <span style="color: #7f7f7f; text-decoration-color: #7f7f7f">[default: no-retry]                                                     </span> <span style="color: #7f7f7f; text-decoration-color: #7f7f7f">│</span>
<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">│</span> <span style="color: #008080; text-decoration-color: #008080; font-weight: bold">--help</span>                      <span style="color: #808000; text-decoration-color: #808000; font-weight: bold">    </span>  Show this message and exit.                                              <span style="color: #7f7f7f; text-decoration-color: #7f7f7f">│</span>
<span style="color: #7f7f7f; text-decoration-color: #7f7f7f">╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯</span>

</pre>
</div>

