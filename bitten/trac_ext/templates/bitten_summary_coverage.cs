<h3>Code Coverage</h3>
<table class="listing coverage">
 <thead><tr><th>Unit</th><th>Lines of Code</th><th>Coverage</th></tr></thead>
 <tbody><?cs
 each:item = data ?><tr><td><a href="<?cs
  var:item.href ?>"><?cs var:item.name ?></a></td><td><?cs
  var:item.loc ?></td><td><?cs var:item.cov ?></td></tr><?cs
 /each ?></tbody>
</table>
