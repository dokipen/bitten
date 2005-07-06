<?cs include:"header.cs" ?>
 <div id="ctxtnav" class="nav"></div>
 <div id="content" class="build">
  <h1><?cs var:title ?></h1><?cs

  if:build.mode == 'overview' ?><?cs
   each:config = build.configs ?>
    <h2><a href="<?cs var:config.href ?>"><?cs var:config.label ?></a></h2><?cs
    if:config.description ?><div class="description"><?cs
     var:config.description ?></div><?cs
    /if ?><?cs
   /each ?><?cs
   if:build.can_create ?><div class="buttons">
    <form method="get" action=""><div>
     <input type="hidden" name="action" value="new" />
     <input type="submit" value="Add configuration" />
    </div></form></div><?cs
   /if ?></div><?cs

  elif:build.mode == 'edit_config' ?>
   <form class="config" method="post" action="">
    <table><tr>
     <td class="name"><label>Name:<br />
      <input type="text" name="name" value="<?cs var:build.config.name ?>" />
     </label></td>
     <td class="label"><label>Label (for display):<br />
      <input type="text" name="label" size="32" value="<?cs
        var:build.config.label ?>" />
     </label></td>
    </tr><tr>
     <td class="active"><label><input type="checkbox" name="active"<?cs
       if:build.config.active ?> checked="checked"<?cs /if ?> /> Active
     </label></td>
     <td class="path"><label>Repository path:<br />
      <input type="text" name="path" size="48" value="<?cs
        var:build.config.path ?>" />
     </label></td>
    </tr><tr>
     <td colspan="2"><fieldset class="iefix">
      <label for="description">Description (you may use <a tabindex="42" href="<?cs
        var:trac.href.wiki ?>/WikiFormatting">WikiFormatting</a> here):</label>
      <p><textarea id="description" name="description" class="wikitext" rows="5" cols="78"><?cs
        var:build.config.description ?></textarea></p>
      <script type="text/javascript" src="<?cs
        var:htdocs_location ?>js/wikitoolbar.js"></script>
     </fieldset></td>
    </tr></table>
    <div class="buttons">
     <input type="hidden" name="action" value="<?cs
       if:build.config.exists ?>edit<?cs else ?>new<?cs /if ?>" />
     <input type="submit" value="<?cs
       if:build.config.exists ?>Save changes<?cs else ?>Create<?cs /if ?>" />
     <input type="submit" name="cancel" value="Cancel" />
    </div>
   </form><?cs
   if:build.config.exists ?><div class="platforms">
    <form class="platforms" method="post" action="">
     <h2>Target Platforms</h2><?cs
      if:len(build.platforms) ?><ul><?cs
       each:platform = build.platforms ?>
        <li><input type="checkbox" name="delete_platform" value="<?cs
         var:platform.id ?>"> <a href="<?cs
         var:platform.href ?>"><?cs var:platform.name ?></a>
        </li><?cs
       /each ?></ul><?cs
      /if ?>
     <div class="buttons">
      <input type="submit" name="new" value="Add target platform" />
      <input type="submit" name="delete" value="Delete selected platforms" />
     </div>
    </form>
   </div><?cs
   /if ?><?cs

  elif:build.mode == 'view_config' ?><ul>
   <li>Active: <?cs if:build.config.active ?>yes<?cs else ?>no<?cs /if ?></li>
   <li>Path: <?cs if:build.config.path ?><a href="<?cs
     var:build.config.browser_href ?>"><?cs
     var:build.config.path ?></a></li><?cs /if ?></ul><?cs
   if:build.config.description ?><div class="description"><?cs
     var:build.config.description ?></div><?cs
   /if ?><?cs
   if:build.config.can_modify ?><div class="buttons">
    <form method="get" action=""><div>
     <input type="hidden" name="action" value="edit" />
     <input type="submit" value="Edit configuration" />
    </div></form><?cs
   /if ?><?cs
   if:len(build.platforms) ?>
    <table class="listing" id="builds"><thead><tr><th>Changeset</th><?cs
    each:platform = build.platforms ?><th><?cs var:platform.name ?><?cs
    /each ?></tr></thead><?cs
    if:len(build.builds) ?><tbody><?cs
     each:rev = build.builds ?><tr>
      <th class="rev" scope="row"><a href="<?cs
        var:rev.href ?>" title="View Changeset">[<?cs
        var:name(rev) ?>]</a></th><?cs
      each:platform = build.platforms ?><?cs
       if:len(rev[platform.id]) ?><td class="<?cs
        var:rev[platform.id].cls ?>"><a href="<?cs
        var:rev[platform.id].href ?>" title="View build results"><?cs
        var:rev[platform.id].slave.name ?></a><br /><?cs
        if:rev[platform.id].status == 'in progress' ?>started <?cs var:rev[platform.id].started_delta ?> ago<?cs
        else ?>took <?cs
         var:rev[platform.id].duration ?></td><?cs
        /if ?><?cs
       else ?><td>&mdash;</td><?cs
       /if ?><?cs
      /each ?></tr><?cs
     /each ?></tbody><?cs
    /if ?></table><?cs
   /if ?></div><?cs

  elif:build.mode == 'edit_platform' ?>
   <form class="platform" method="post" action="">
    <div class="field"><label>Name:<br />
     <input type="text" name="name" value="<?cs var:build.platform.name ?>" />
    </label></div>
    <h2>Rules</h2>
    <table><thead><tr>
     <th>Property name</th><th>Match pattern</th>
    </tr></thead><tbody><?cs
     each:rule = build.platform.rules ?><tr>
      <td><input type="text" name="property_<?cs var:name(rule) ?>" value="<?cs
       var:rule.property ?>" /></td>
      <td><input type="text" name="pattern_<?cs var:name(rule) ?>" value="<?cs
       var:rule.pattern ?>" /></td>
      <td><input type="submit" name="rm_rule_<?cs
        var:name(rule) ?>" value="-" /><input type="submit" name="add_rule_<?cs
        var:name(rule) ?>" value="+" />
      </td>
     </tr><?cs /each ?>
    </tbody></table>
    <div class="buttons">
     <form method="get" action=""><div>
     <input type="hidden" name="action" value="<?cs
       if:build.platform.exists ?>edit<?cs else ?>new<?cs /if ?>" />
      <input type="hidden" name="platform" value="<?cs
       var:build.platform.id ?>" />
      <input type="submit" value="<?cs
       if:build.platform.exists ?>Save changes<?cs else ?>Add platform<?cs
       /if ?>" />
      <input type="submit" name="cancel" value="Cancel" />
     </div></form>
    </div>
   </form><?cs

  elif:build.mode == 'view_build' ?>
   <p class="trigger">Triggered by: Changeset <a href="<?cs
     var:build.chgset_href ?>">[<?cs var:build.rev ?>]</a> of <a href="<?cs
     var:build.config.href ?>"><?cs var:build.config.name ?></a></p>
   <p class="slave">Built by: <strong title="<?cs
     var:build.slave.ip_address ?>"><?cs var:build.slave.name ?></strong> (<?cs
     var:build.slave.os ?> <?cs var:build.slave.os.version ?><?cs
     if:build.slave.machien ?> on <?cs var:build.slave.machine ?><?cs
     /if ?>)</p>
   <p class="time">Completed: <?cs var:build.started ?> (<?cs
     var:build.started_delta ?> ago)<br />Took: <?cs var:build.duration ?></p><?cs
  each:step = build.steps ?>
   <h2><?cs var:step.name ?></h2>
   <p><?cs var:step.description ?></p>
   <pre class="log"><?cs var:step.log ?></pre><?cs
  /each ?><?cs
  /if ?>

 </div>
<?cs include:"footer.cs" ?>
