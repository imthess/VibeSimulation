import com.cburch.logisim.file.*;
import com.cburch.logisim.circuit.*;
import com.cburch.logisim.comp.*;
import com.cburch.logisim.data.*;
import java.io.File;
public class Dump { public static void main(String[] a) throws Exception {
  Loader loader = new Loader(null);
  LogisimFile f = loader.openLogisimFile(new File(a[0]));
  Circuit c = f.getMainCircuit();
  for (Component comp : c.getNonWires()) {
    Bounds b = comp.getBounds(); Location l = comp.getLocation();
    StringBuilder sb = new StringBuilder("COMP " + comp.getFactory().getName() + " loc=" + l.getX() + "," + l.getY() + " bounds=" + b.getX() + "," + b.getY() + "," + b.getWidth() + "," + b.getHeight());
    AttributeSet as = comp.getAttributeSet();
    for (Attribute<?> at : as.getAttributes()) sb.append(" [" + at.getName() + "=" + as.getValue(at) + "]");
    System.out.println(sb);
    int i = 0;
    for (EndData e : comp.getEnds()) { Location p = e.getLocation(); System.out.println("  END " + i++ + " " + (p.getX() - l.getX()) + "," + (p.getY() - l.getY()) + " " + (e.isInput() ? "in" : "") + (e.isOutput() ? "out" : "") + " w=" + e.getWidth().getWidth()); }
  }
}}
