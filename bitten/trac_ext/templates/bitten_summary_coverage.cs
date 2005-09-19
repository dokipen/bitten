<h3>Code Coverage</h3>
<table class="listing coverage">
 <thead><tr><th class="name">Unit</th><th class="loc">Lines of Code</th>
 <th clsas="cov">Coverage</th></tr></thead>
 <tbody><?cs
 each:item = data ?><tr><td class="name"><a href="<?cs
  var:item.href ?>"><?cs var:item.name ?></a></td><td class="loc"><?cs
  var:item.loc ?></td><td class="cov"><?cs var:item.cov ?>%</td></tr><?cs
 /each ?></tbody>
</table>
