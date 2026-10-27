import com.cburch.logisim.file.*;
import com.cburch.logisim.circuit.*;
import com.cburch.logisim.comp.*;
import com.cburch.logisim.data.*;
import java.io.File;
public class Widths { public static void main(String[] a) throws Exception {
  Loader loader = new Loader(null);
  LogisimFile f = loader.openLogisimFile(new File(a[0]));
  Circuit c = f.getMainCircuit();
  for (Component comp : c.getNonWires()) {
    Location l = comp.getLocation();
    System.out.println("COMP " + comp.getFactory().getName() + " " + l);
    for (EndData e : comp.getEnds()) { Location p = e.getLocation();
      System.out.println("   end " + p + " w=" + e.getWidth().getWidth() + " netw=" + c.getWidth(p).getWidth() + " conn=" + c.isConnected(p, comp)); }
  }
  System.exit(0);
}}
