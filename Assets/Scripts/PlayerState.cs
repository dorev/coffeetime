using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class PlayerState : MonoBehaviour
{
    public CoffeeBar coffeeBar;
    public int maxCoffee = 100;
    public int currentCoffee;

    void Start()
    {
        coffeeBar.SetMaxCoffee(maxCoffee);
        currentCoffee = maxCoffee;
    }

    // Update is called once per frame
    void Update()
    {
        if(Input.GetKeyDown(KeyCode.Space))
        {
            DrinkCoffee(10);
        }
    }

    void DrinkCoffee(int coffeeAmount)
    {
        Debug.Log("Gulp! Drinks " + coffeeAmount + " coffee.");
        currentCoffee -= coffeeAmount;
        coffeeBar.SetCoffee(currentCoffee);
    }
}
