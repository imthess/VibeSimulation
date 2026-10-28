import com.cburch.logisim.file.*;
import com.cburch.logisim.circuit.*;
import com.cburch.logisim.comp.*;
import com.cburch.logisim.data.*;
import com.cburch.logisim.proj.*;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.File;
import javax.imageio.ImageIO;
public class Render { public static void main(String[] a) throws Exception {
  Loader loader = new Loader(null);
  LogisimFile f = loader.openLogisimFile(new File(a[0]));
  Circuit c = f.getMainCircuit();
  Bounds b = c.getBounds();
  int sc = Integer.parseInt(a[2]);
  BufferedImage img = new BufferedImage((b.getWidth() + 60) * sc, (b.getHeight() + 60) * sc, BufferedImage.TYPE_INT_RGB);
  Graphics2D g = img.createGraphics();
  g.setColor(Color.WHITE); g.fillRect(0, 0, img.getWidth(), img.getHeight());
  g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
  g.scale(sc, sc); g.translate(30 - b.getX(), 30 - b.getY());
  Project proj = new Project(f); CircuitState st = proj.getCircuitState(c);
  ComponentDrawContext ctx = new ComponentDrawContext(new javax.swing.JPanel(), c, st, g, g);
  c.draw(ctx, null);
  ImageIO.write(img, "png", new File(a[1])); System.exit(0);
}}
