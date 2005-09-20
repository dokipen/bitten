<h3>Test Results</h3>
<table class="listing tests">
 <thead><tr>
  <th>Test Fixture</th><th>Total</th>
  <th>Failures</th><th>Errors</th>
 </tr></thead>
 <tbody><?cs
 each:item = data ?><tr><td><?cs
  if:item.href ?><a href="<?cs var:item.href ?>"><?cs var:item.name ?></a><?cs
  else ?><?cs var:item.name ?><?cs
  /if ?></td><td><?cs
  var:#item.num_success + #item.num_failure + #item.num_error ?></td><td><?cs
  var:item.num_failure ?></td><td><?cs
  var:item.num_error ?></td></tr><?cs
 /each ?></tbody>
</table>
