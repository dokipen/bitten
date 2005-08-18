<?cs include:"header.cs" ?>
 <div id="ctxtnav" class="nav"></div>
 <div id="content" class="build">
  <h1><?cs var:title ?></h1>
  <p class="trigger">Triggered by: Changeset <a href="<?cs
    var:build.chgset_href ?>">[<?cs var:build.rev ?>]</a> of <a href="<?cs
    var:build.config.href ?>"><?cs var:build.config.name ?></a></p>
  <p class="slave">Built by: <strong title="<?cs
    var:build.slave.ip_address ?>"><?cs var:build.slave.name ?></strong> (<?cs
    var:build.slave.os ?> <?cs var:build.slave.os.version ?><?cs
    if:build.slave.machine ?> on <?cs var:build.slave.machine ?><?cs
    /if ?>)</p>
  <p class="time">Completed: <?cs var:build.started ?> (<?cs
    var:build.started_delta ?> ago)<br />Took: <?cs var:build.duration ?></p><?cs
  each:step = build.steps ?>
   <h2 id="<?cs var:step.name ?>"><?cs var:step.name ?> (<?cs
     var:step.duration ?>)</h2><?cs
   if:len(step.reports) ?>
    <div class="reports"><h3>Generated Reports</h3><ul><?cs
     each:report = step.reports ?><li class="<?cs
       var:report.type ?>"><a href="<?cs var:report.href ?>"><?cs
       var:report.type ?></a></li><?cs
     /each ?>
    </ul></div><?cs
   /if ?>
   <p><?cs var:step.description ?></p>
   <div class="log"><?cs
    each:item = step.log ?><code class="<?cs var:item.level ?>"><?cs
     var:item.message ?></code><br /><?cs
    /each ?></div><?cs
  /each ?>
 </div>
<?cs include:"footer.cs" ?>
