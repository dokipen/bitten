<?cs include:"header.cs" ?>
 <script type="text/javascript" src="<?cs
   var:chrome.href ?>/bitten/tabset.js"></script>
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
     var:step.duration ?>)</h2>
   <p><?cs var:step.description ?></p>
   <div id="<?cs var:step.name ?>_tabs">
    <div class="tab"><h3>Log</h3><div class="log"><?cs
     each:item = step.log ?><code class="<?cs var:item.level ?>"><?cs
      var:item.message ?></code><br /><?cs
     /each ?></div>
    </div><?cs
    each:report = step.reports ?><?cs
     if:report.summary ?>
      <div class="tab report <?cs var:report.type ?>">
       <?cs var:report.summary ?>
      </div><?cs
     /if ?><?cs
    /each ?>
   </div>
   <script type="text/javascript">
     makeTabSet(document.getElementById("<?cs var:step.name ?>_tabs"));
   </script><?cs
  /each ?>
 </div>
<?cs include:"footer.cs" ?>
