<h3>Test Results</h3>
<table class="listing tests">
 <thead><tr>
  <th>Test Fixture</th><th>Total</th>
  <th>Failures</th><th>Errors</th>
 </tr></thead>
 <tbody><?cs
 each:item = data ?><tr<?cs
  if:item.num_failure != 0 || item.num_error != 0 ?> class="failed"<?cs
  /if ?>><th><?cs
  if:item.href ?><a href="<?cs var:item.href ?>"><?cs var:item.name ?></a><?cs
  else ?><?cs var:item.name ?><?cs
  /if ?></th><td><?cs
  var:#item.num_success + #item.num_failure + #item.num_error ?></td><td><?cs
  var:item.num_failure ?></td><td><?cs
  var:item.num_error ?></td></tr><?cs
 /each ?></tbody>
 <tbody class="totals"><tr>
  <th>Total</th>
  <td><?cs var:totals.success ?></td>
  <td><?cs var:totals.failure ?></td><td><?cs var:totals.error ?></td>
 </tr></tbody>
</table>
